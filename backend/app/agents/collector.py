"""Agent 2 — Collector. No LLM.

Fetches whitelisted feeds for a genre, applies the freshness rule, respects
robots.txt, extracts full text, and splits it into citable passages.

Three rules are structural here rather than advisory:

- Only sources that are enabled in config/sources.yaml are ever contacted,
  and a source is only enabled once its terms have been confirmed.
- robots.txt is consulted before an article is fetched, not after.
- An item without a reliable timestamp is dropped, never guessed at.

A failure anywhere is recorded and the genre continues. One dead feed must
not cost the section.
"""

from __future__ import annotations

from datetime import datetime

from app.clock import now_utc
from app.config.loader import load_sources
from app.config.schemas import GenreKey, SourcesConfig
from app.sources.extract import extract_article
from app.sources.feeds import parse_feed
from app.sources.fetch import Fetcher, FetchError
from app.sources.freshness import freshness_verdict
from app.sources.robots import RobotsPolicy
from app.sources.schemas import (
    CollectedArticle,
    CollectionResult,
    Dropped,
    DropReason,
    FeedItem,
)

DEFAULT_MAX_ARTICLES = 40


def _round_robin(items: list[FeedItem]) -> list[FeedItem]:
    """Interleave feed items by source, each source's own relative (most-
    recent-first) order preserved within its own turn."""
    buckets: dict[str, list[FeedItem]] = {}
    order: list[str] = []
    for item in items:
        if item.source_key not in buckets:
            buckets[item.source_key] = []
            order.append(item.source_key)
        buckets[item.source_key].append(item)

    result: list[FeedItem] = []
    while any(buckets[key] for key in order):
        for key in order:
            if buckets[key]:
                result.append(buckets[key].pop(0))
    return result


class Collector:
    def __init__(
        self,
        *,
        fetcher: Fetcher,
        robots: RobotsPolicy,
        sources: SourcesConfig | None = None,
        max_articles: int = DEFAULT_MAX_ARTICLES,
    ) -> None:
        self._fetcher = fetcher
        self._robots = robots
        self._sources = sources or load_sources()
        self._max_articles = max_articles

    def collect(
        self,
        genre: GenreKey,
        *,
        now: datetime | None = None,
        max_articles: int | None = None,
    ) -> CollectionResult:
        """`max_articles`, when given, overrides the cap for this call only —
        the Ranker uses this to ask for wider coverage (still whitelisted
        sources only, still the same freshness window) when a cluster it
        would otherwise drop for thin sourcing might be one article away
        from clearing the corroboration gate."""
        reference = now or now_utc()
        cap = max_articles if max_articles is not None else self._max_articles
        articles: list[CollectedArticle] = []
        dropped: list[Dropped] = []

        items, feed_failures = self._gather(genre)
        dropped.extend(feed_failures)
        # Interleaved by source, not left in feed-then-feed order: otherwise
        # one high-volume source can reach `cap` on its own before any other
        # enabled source is even looked at. Found live: The Hindu's business
        # feed alone supplied the entire 40-article cap for "business" one
        # day, so Livemint and Economic Times — two of the five enabled
        # sources — were never fetched at all, not filtered, just never
        # reached.
        items = _round_robin(items)

        seen_urls: set[str] = set()
        seen_hashes: set[str] = set()

        for item in items:
            if len(articles) >= cap:
                break

            if item.url in seen_urls:
                dropped.append(self._drop(item, DropReason.DUPLICATE_URL))
                continue
            seen_urls.add(item.url)

            stale = freshness_verdict(item.published_at, now=reference)
            if stale is not None:
                dropped.append(self._drop(item, stale))
                continue

            if not self._robots.allows(item.url):
                dropped.append(self._drop(item, DropReason.ROBOTS_DISALLOWED))
                continue

            try:
                response = self._fetcher.get(item.url)
            except FetchError as exc:
                dropped.append(self._drop(item, DropReason.FETCH_FAILED, str(exc)))
                continue

            extraction = extract_article(response.text, url=item.url)
            if extraction is None:
                # Covers extraction failure, consent walls, and paywall
                # teasers alike: too little text to report from.
                dropped.append(self._drop(item, DropReason.TOO_SHORT))
                continue

            if extraction.content_hash in seen_hashes:
                dropped.append(self._drop(item, DropReason.DUPLICATE_CONTENT))
                continue
            seen_hashes.add(extraction.content_hash)

            # published_at is not None: freshness_verdict already rejected None.
            assert item.published_at is not None
            articles.append(
                CollectedArticle(
                    source_key=item.source_key,
                    genre=item.genre,
                    url=item.url,
                    canonical_url=extraction.canonical_url,
                    title=extraction.title or item.title,
                    author=extraction.author,
                    published_at=item.published_at,
                    fetched_at=reference,
                    text=extraction.text,
                    passages=extraction.passages,
                    content_hash=extraction.content_hash,
                )
            )

        return CollectionResult(genre=genre, articles=articles, dropped=dropped)

    # ------------------------------------------------------------------ feeds

    def _gather(self, genre: GenreKey) -> tuple[list[FeedItem], list[Dropped]]:
        items: list[FeedItem] = []
        failures: list[Dropped] = []

        for source, feed in self._sources.feeds_for(genre):
            url = str(feed.url)
            try:
                response = self._fetcher.get(url)
            except FetchError as exc:
                failures.append(
                    Dropped(
                        url=url,
                        source_key=source.key,
                        reason=DropReason.FEED_FAILED,
                        detail=str(exc),
                    )
                )
                continue
            items.extend(
                parse_feed(
                    response.content,
                    source_key=source.key,
                    genre=genre,
                    fallback_timezone=source.fallback_timezone,
                )
            )

        return items, failures

    @staticmethod
    def _drop(item: FeedItem, reason: DropReason, detail: str | None = None) -> Dropped:
        return Dropped(url=item.url, source_key=item.source_key, reason=reason, detail=detail)

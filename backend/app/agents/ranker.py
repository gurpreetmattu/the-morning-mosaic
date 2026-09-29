"""Agent 3 — Ranker. LLM for clustering, code for everything that matters.

The model proposes which articles describe the same event. It does not score,
rank, or decide what is publishable: corroboration and scoring are
deterministic (see app/agents/ranking.py), so a model failure degrades
grouping quality but can never let an under-sourced story through or tilt the
order of the pool.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Protocol

from app.agents.ranking import (
    cluster_by_title,
    conflicting_facts,
    corroboration_for,
    meets_gate,
    reconcile_clusters,
    score_cluster,
)
from app.agents.schemas import (
    Corroboration,
    PoolDropped,
    PoolDropReason,
    PooledStory,
    StoryPool,
)
from app.clock import now_utc
from app.config.loader import load_genres, load_sources
from app.config.schemas import GenreKey, GenresConfig, SourcesConfig
from app.llm.client import LlmClient, Message, strip_json_fence
from app.llm.errors import LlmError
from app.llm.guard import redact_identifiers
from app.llm.prompts import ranker_v1
from app.sources.schemas import CollectedArticle, CollectionResult

# Enough of the opening text to tell two events apart, without paying for the
# whole article on a grouping task.
EXCERPT_CHARS = 300

# Roughly double app.agents.collector.Collector's own default cap, for the
# one retry with wider coverage below. Whitelisted sources only, same
# freshness window — CLAUDE.md's 24-hour rule is never loosened to rescue a
# story; only how much of that same window's feed backlog gets fetched.
COVERAGE_RETRY_MAX_ARTICLES = 80

# A single well-corroborated event can have far more source articles than
# any one Writer prompt should carry. corroboration_for/score_cluster still
# see every member below — this only caps how many of them make it into
# the PooledStory the Writer actually reads and cites, so corroboration
# stays a fact about the real cluster, not about the capped subset. Found
# the hard way: a real 9-article cluster sent ~45,000 characters to the
# Writer in one call and exceeded every pinned model's per-request token
# budget on the free tier this project runs on.
MAX_ARTICLES_PER_STORY = 4


def _prioritised(
    members: list[CollectedArticle], tiers: Mapping[str, int]
) -> list[CollectedArticle]:
    """Tier-1 sources first, then most recent — so capping a cluster keeps
    its most credible, freshest coverage rather than an arbitrary slice."""
    return sorted(members, key=lambda a: (tiers.get(a.source_key, 3), -a.published_at.timestamp()))


class CollectorLike(Protocol):
    """Structural, so a test can substitute a stub without a network."""

    def collect(
        self,
        genre: GenreKey,
        *,
        now: datetime | None = None,
        max_articles: int | None = None,
    ) -> CollectionResult: ...


class Ranker:
    def __init__(
        self,
        *,
        llm: LlmClient,
        genres: GenresConfig | None = None,
        sources: SourcesConfig | None = None,
        collector: CollectorLike | None = None,
        coverage_retry_max_articles: int = COVERAGE_RETRY_MAX_ARTICLES,
    ) -> None:
        self._llm = llm
        self._genres = genres or load_genres()
        self._tiers = {source.key: source.tier for source in (sources or load_sources()).sources}
        self._collector = collector
        self._coverage_retry_max_articles = coverage_retry_max_articles

    def rank(self, collected: CollectionResult, *, now: datetime | None = None) -> StoryPool:
        reference = now or now_utc()
        pool = self._build_pool(collected, reference)

        if not self._worth_asking_for_more_coverage(collected, pool):
            return pool

        assert self._collector is not None  # narrowed by the check above
        widened = self._collector.collect(
            collected.genre, now=reference, max_articles=self._coverage_retry_max_articles
        )
        if len(widened.articles) <= len(collected.articles):
            # Nothing new turned up; the first pass already stands.
            return pool

        rebuilt = self._build_pool(widened, reference)
        return rebuilt.model_copy(update={"requested_more_coverage": True})

    def _worth_asking_for_more_coverage(self, collected: CollectionResult, pool: StoryPool) -> bool:
        if self._collector is None:
            return False
        genre = self._genres.by_key()[collected.genre]
        if genre.corroboration != "strict":
            return False
        return any(
            dropped.reason is PoolDropReason.INSUFFICIENT_CORROBORATION for dropped in pool.dropped
        )

    def _build_pool(self, collected: CollectionResult, reference: datetime) -> StoryPool:
        genre = self._genres.by_key()[collected.genre]
        strict = genre.corroboration == "strict"

        if not collected.articles:
            return StoryPool(genre=collected.genre)

        articles = {f"a{index}": a for index, a in enumerate(collected.articles, start=1)}
        groups, labels, used_fallback = self._cluster(articles)

        scored: list[tuple[float, str, list[CollectedArticle]]] = []
        dropped: list[PoolDropped] = []

        for index, member_ids in enumerate(groups):
            members = [articles[member_id] for member_id in member_ids]
            label = labels.get(index) or members[0].title[:80]

            # Checked before the corroboration gate, and regardless of it:
            # a conflict is a reason to drop on its own, not something more
            # sourcing could excuse.
            if conflicting_facts(members):
                dropped.append(
                    PoolDropped(
                        event_label=label,
                        source_keys=sorted({m.source_key for m in members}),
                        reason=PoolDropReason.CONFLICTING_FACTS,
                    )
                )
                continue

            corroboration = corroboration_for(members, self._tiers)

            if not meets_gate(corroboration, strict=strict):
                dropped.append(
                    PoolDropped(
                        event_label=label,
                        source_keys=sorted({m.source_key for m in members}),
                        reason=PoolDropReason.INSUFFICIENT_CORROBORATION,
                    )
                )
                continue

            scored.append((score_cluster(members, self._tiers, now=reference), label, members))

        # Highest score first; newest first as a stable, non-topical tiebreak.
        scored.sort(
            key=lambda entry: (
                -entry[0],
                -max(a.published_at for a in entry[2]).timestamp(),
                entry[1],
            )
        )

        stories: list[PooledStory] = []
        for position, (score, label, members) in enumerate(scored, start=1):
            corroboration = corroboration_for(members, self._tiers)
            if position > genre.pool_size:
                dropped.append(
                    PoolDropped(
                        event_label=label,
                        source_keys=sorted({m.source_key for m in members}),
                        reason=PoolDropReason.BELOW_POOL_CAP,
                    )
                )
                continue
            stories.append(
                PooledStory(
                    event_label=label,
                    articles=_prioritised(members, self._tiers)[:MAX_ARTICLES_PER_STORY],
                    corroboration=corroboration,
                    hedged=corroboration == Corroboration.TIER3_ONLY,
                    score=score,
                    rank=position,
                )
            )

        return StoryPool(
            genre=collected.genre,
            stories=stories,
            dropped=dropped,
            used_fallback_clustering=used_fallback,
        )

    # -------------------------------------------------------------- clustering

    def _cluster(
        self, articles: dict[str, CollectedArticle]
    ) -> tuple[list[list[str]], dict[int, str], bool]:
        """Returns (groups, labels by group index, whether fallback was used)."""
        if len(articles) == 1:
            only = next(iter(articles))
            return [[only]], {0: articles[only].title[:80]}, False

        try:
            proposed, labels = self._propose(articles)
        except (LlmError, ValueError, KeyError, TypeError):
            return cluster_by_title(articles), {}, True

        groups = reconcile_clusters(proposed, articles)
        # Labels are positional in the proposal; reconciliation can drop empty
        # groups, so only keep labels for groups that survived intact.
        kept = {
            index: labels[index]
            for index in range(min(len(groups), len(labels)))
            if index in labels
        }
        return groups, kept, False

    def _propose(
        self, articles: dict[str, CollectedArticle]
    ) -> tuple[list[list[str]], dict[int, str]]:
        rendered = "\n".join(
            ranker_v1.render_article(
                article_id,
                redact_identifiers(article.title),
                redact_identifiers(article.passages[0].text[:EXCERPT_CHARS]),
            )
            for article_id, article in articles.items()
        )
        result = self._llm.complete(
            "ranker",
            [
                Message(role="system", content=ranker_v1.SYSTEM),
                Message(
                    role="user",
                    content=ranker_v1.USER_TEMPLATE.format(count=len(articles), articles=rendered),
                ),
            ],
            json_object=True,
            prompt_version=ranker_v1.VERSION,
        )

        payload = json.loads(strip_json_fence(result.text))
        proposed: list[list[str]] = []
        labels: dict[int, str] = {}
        for cluster in payload["clusters"]:
            ids = [str(article_id) for article_id in cluster["article_ids"]]
            labels[len(proposed)] = str(cluster.get("event", ""))[:120]
            proposed.append(ids)
        return proposed, labels

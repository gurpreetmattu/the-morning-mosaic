"""One story, one genre.

Genres collect and rank independently, so the same event can land in two
pools (a model launch is both AI and Technology news). Printing it twice reads
as padding and wastes a verification pass. This module decides, in code and
before anything is written, which genre keeps each shared story.

Deterministic on purpose: genres run in parallel, so "whoever gets there first"
would change from run to run. Instead the genres are visited in the fixed
`dedup_priority` order from config/genres.yaml and the first one to hold a story
keeps it. No LLM, so it cannot be argued into keeping a duplicate.

What counts as the same story is deliberately the same evidence the Ranker
already uses inside a genre (app/agents/ranking.py): a shared article, a near-
identical headline, or heavily overlapping text. When unsure the stories are
treated as different, because publishing two near-duplicates is a quality
problem, while merging two different events would silently lose one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.agents.ranking import (
    SYNDICATION_OVERLAP_THRESHOLD,
    TITLE_SIMILARITY_THRESHOLD,
    text_overlap,
    title_similarity,
)
from app.agents.schemas import PooledStory
from app.config.schemas import GenreKey


@dataclass(frozen=True)
class ArticleMark:
    """What is compared about one source article."""

    url: str
    title: str
    # Absent for stories already stored: raw text is purged after 30 days, so the
    # comparison for those rests on the URL and headline alone.
    text: str | None = None


@dataclass(frozen=True)
class StoryMark:
    """A story reduced to what matching needs."""

    genre: GenreKey
    label: str
    articles: tuple[ArticleMark, ...]


@dataclass(frozen=True)
class CrossGenreResult:
    kept: dict[GenreKey, list[PooledStory]]
    # Event labels removed from each genre. Internal labels only, never published.
    dropped: dict[GenreKey, list[str]] = field(default_factory=dict)

    def dropped_count(self, genre: GenreKey) -> int:
        return len(self.dropped.get(genre, []))


def _normal_url(url: str) -> str:
    """Scheme, tracking query and fragment do not make a different article."""
    parts = urlsplit(url.strip().lower())
    return f"{parts.netloc}{parts.path.rstrip('/')}"


def mark_of(genre: GenreKey, story: PooledStory) -> StoryMark:
    articles: list[ArticleMark] = []
    for article in story.articles:
        articles.append(ArticleMark(url=article.url, title=article.title, text=article.text))
        if article.canonical_url:
            articles.append(ArticleMark(url=article.canonical_url, title=article.title))
    return StoryMark(genre=genre, label=story.event_label, articles=tuple(articles))


def _same_article(left: ArticleMark, right: ArticleMark) -> bool:
    if _normal_url(left.url) == _normal_url(right.url):
        return True
    if title_similarity(left.title, right.title) >= TITLE_SIMILARITY_THRESHOLD:
        return True
    if left.text and right.text:
        return text_overlap(left.text, right.text) >= SYNDICATION_OVERLAP_THRESHOLD
    return False


def same_story(left: StoryMark, right: StoryMark) -> bool:
    return any(_same_article(a, b) for a in left.articles for b in right.articles)


def assign_owners(
    pools: Mapping[GenreKey, Sequence[PooledStory]],
    *,
    order: Sequence[GenreKey],
    published: Sequence[StoryMark] = (),
) -> CrossGenreResult:
    """Keep each shared story in exactly one genre.

    `order` is the genre priority, highest first. Genres in `pools` that it does
    not mention come last, in the pools' own order. `published` are stories already
    out for this edition (a late update): they keep their genre, so a new candidate
    elsewhere that repeats one is dropped. Stories already in the candidate's own
    genre are the late update's own concern (it matches by content hash) and are
    ignored here.
    """
    rank = {genre: index for index, genre in enumerate(order)}
    visiting = sorted(pools, key=lambda genre: rank.get(genre, len(rank)))

    claimed: list[StoryMark] = list(published)
    kept: dict[GenreKey, list[PooledStory]] = {}
    dropped: dict[GenreKey, list[str]] = {}

    for genre in visiting:
        survivors: list[PooledStory] = []
        for story in pools[genre]:
            mark = mark_of(genre, story)
            if any(other.genre != genre and same_story(mark, other) for other in claimed):
                dropped.setdefault(genre, []).append(story.event_label)
                continue
            survivors.append(story)
            claimed.append(mark)
        kept[genre] = survivors

    # Callers read results by genre in their own order, so return every input genre.
    return CrossGenreResult(kept={genre: kept[genre] for genre in pools}, dropped=dropped)

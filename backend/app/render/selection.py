"""Per-user story selection. No LLM, by design.

CLAUDE.md: "No per-user LLM generation. Personalization = selecting and
ordering stories from verified pools, done in code."

That is not a performance decision. Every story in a pool has already been
written, cited and verified; re-generating per reader would mean re-verifying
per reader, and nothing would guarantee two readers saw the same facts. Here
the only per-user freedom is which of the verified stories appear and in what
order.

Four signals, in decreasing strength:

1. a followed keyword matching the story's tags, which CLAUDE.md says should
   "replace lower-ranked ones within that cap" — so it outranks everything;
2. the reader's learned topic preferences, from their own feedback;
3. their edition preference, nudging India-relevant stories up or down;
4. the pool rank the Ranker computed, which is the default order.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.loader import load_genres, load_sources
from app.config.schemas import GenreKey, GenresConfig
from app.models.content import Article, ClusterArticle, Source, Story, StoryTag
from app.models.enums import EditionPreference, StoryStatus, TagKind

# A followed keyword dominates: the reader asked for this explicitly.
KEYWORD_BONUS = 100.0
# Learned from thumbs up/down, so meaningful but not overriding.
PREFERENCE_WEIGHT = 2.0
# Edition preference is a nudge, not a filter: a global reader still sees big
# Indian stories, just lower.
INDIA_ADJUSTMENT = 3.0

_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Reader:
    """Everything selection needs about a subscriber, and nothing more."""

    id: uuid.UUID
    first_name: str
    genres: tuple[GenreKey, ...]
    keywords: frozenset[str] = frozenset()
    edition_preference: EditionPreference = EditionPreference.MIXED
    # (genre, topic_tag) -> score, aggregated from this reader's feedback.
    topic_scores: Mapping[tuple[str, str], float] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceLink:
    name: str
    url: str


@dataclass(frozen=True)
class Candidate:
    story_id: uuid.UUID
    genre: GenreKey
    headline: str
    summary: str
    one_liner: str | None
    why_this_matters: str | None
    hedged: bool
    india_relevance: bool
    pool_rank: int
    topic_tags: frozenset[str]
    entity_tags: frozenset[str]
    # Every story links to its sources, in the email as well as the archive.
    sources: tuple[SourceLink, ...] = ()


# CLAUDE.md: "Music releases: official label/platform announcements covered
# by whitelisted sources" — not a separate API like movie releases (TMDB),
# but drawn straight from the day's own verified music stories.
# album-releases/single-releases are in config/genres.yaml's own closed
# topic-tag taxonomy for the music genre.
MUSIC_RELEASE_TAGS = frozenset({"album-releases", "single-releases"})
MUSIC_RELEASES_LIMIT = 3


def _tokens(text: str) -> frozenset[str]:
    return frozenset(_WORD.findall(text.lower()))


def ai_tool_from_candidates(
    genre: str, candidates: Sequence[Candidate]
) -> dict[str, object] | None:
    """CLAUDE.md: "AI tool of the day" is picked from tools covered in that
    day's verified AI stories. Rather than guessing which entity tag names an
    actual tool, this features the day's top-ranked verified AI story itself
    — deterministic, and grounded in exactly the same already-checked
    headline/one-liner/source every reader already sees in the section below.

    Shared between the once-per-revision build render (`SectionRenderer`,
    used for the public archive) and the per-reader delivered email
    (`EmailRenderer`) — this is never personalised, only the story selection
    is, so both must show the same pick from the same logic.
    """
    if genre != "ai" or not candidates:
        return None
    top = min(candidates, key=lambda c: c.pool_rank)
    if not top.sources:
        return None
    blurb = top.one_liner or top.summary
    return {
        "headline": top.headline,
        "blurb": blurb,
        "source": {"name": top.sources[0].name, "url": top.sources[0].url},
    }


def music_releases_from_candidates(
    genre: str, candidates: Sequence[Candidate]
) -> list[dict[str, object]]:
    """Shared between the build-time and per-reader delivered-email render
    paths — see `ai_tool_from_candidates`."""
    if genre != "music":
        return []
    picked = [c for c in candidates if MUSIC_RELEASE_TAGS & c.topic_tags]
    releases: list[dict[str, object]] = []
    for candidate in picked[:MUSIC_RELEASES_LIMIT]:
        if not candidate.sources:
            continue
        source = candidate.sources[0]
        releases.append(
            {"headline": candidate.headline, "source": {"name": source.name, "url": source.url}}
        )
    return releases


def matches_keywords(candidate: Candidate, keywords: frozenset[str]) -> bool:
    """A keyword matches a topic tag exactly, or a word inside an entity tag.

    Entity tags are proper nouns, so a reader following "isro" should match
    "ISRO" inside a longer name; topic tags come from a fixed taxonomy, so an
    exact match is right there.
    """
    if not keywords:
        return False

    normalised = {keyword.strip().lower() for keyword in keywords if keyword.strip()}
    if normalised & {tag.lower() for tag in candidate.topic_tags}:
        return True

    entity_words = (
        set().union(*(_tokens(tag) for tag in candidate.entity_tags))
        if (candidate.entity_tags)
        else set()
    )
    return bool(normalised & entity_words)


def score(candidate: Candidate, reader: Reader, *, pool_size: int) -> float:
    """Higher is better. Deterministic: the same inputs always order the same."""
    # The Ranker's order is the baseline, inverted so rank 1 scores highest.
    total = float(max(pool_size + 1 - candidate.pool_rank, 0))

    if matches_keywords(candidate, reader.keywords):
        total += KEYWORD_BONUS

    for tag in candidate.topic_tags:
        total += PREFERENCE_WEIGHT * reader.topic_scores.get((candidate.genre, tag), 0.0)

    if candidate.india_relevance:
        if reader.edition_preference is EditionPreference.INDIA:
            total += INDIA_ADJUSTMENT
        elif reader.edition_preference is EditionPreference.GLOBAL:
            total -= INDIA_ADJUSTMENT

    return total


def select_for_reader(
    candidates: Sequence[Candidate],
    reader: Reader,
    *,
    genres: GenresConfig | None = None,
) -> dict[GenreKey, list[Candidate]]:
    """Pick and order each subscribed genre's stories for one reader."""
    settings = (genres or load_genres()).by_key()
    chosen: dict[GenreKey, list[Candidate]] = {}

    for genre in reader.genres:
        genre_settings = settings[genre]
        pool = [c for c in candidates if c.genre == genre]
        if len(pool) < genre_settings.min_stories:
            # Too thin to publish as a section; the caller shows a quiet note.
            continue

        pool_sorted = sorted(
            pool,
            key=lambda c: (
                -score(c, reader, pool_size=genre_settings.pool_size),
                c.pool_rank,
                str(c.story_id),
            ),
        )
        chosen[genre] = pool_sorted[: genre_settings.max_stories]

    return chosen


# --------------------------------------------------------------- loading


def load_candidates(
    session: Session, *, edition_date: date, genres: Sequence[GenreKey]
) -> list[Candidate]:
    """Every verified story available for these genres on this date."""
    if not genres:
        return []

    stories = list(
        session.scalars(
            select(Story).where(
                Story.edition_date == edition_date,
                Story.genre.in_(list(genres)),
                Story.status == StoryStatus.VERIFIED,
            )
        )
    )
    return _candidates_from_stories(session, stories)


def load_week_candidates(session: Session, *, dates: Sequence[date]) -> list[Candidate]:
    """Every verified story, any genre, across several days.

    Backs the weekend edition's "longer reads" and "weekly recap"
    (`app/render/weekend.py`), which look back across the week rather than
    at one day. Ordered deterministically, since callers pick a stable-sized
    slice of the result rather than consuming all of it.
    """
    if not dates:
        return []

    stories = list(
        session.scalars(
            select(Story)
            .where(Story.edition_date.in_(list(dates)), Story.status == StoryStatus.VERIFIED)
            .order_by(Story.edition_date, Story.genre, Story.pool_rank, Story.id)
        )
    )
    return _candidates_from_stories(session, stories)


def _candidates_from_stories(session: Session, stories: Sequence[Story]) -> list[Candidate]:
    if not stories:
        return []

    tags: dict[uuid.UUID, dict[TagKind, set[str]]] = {}
    for tag in session.scalars(
        select(StoryTag).where(StoryTag.story_id.in_([story.id for story in stories]))
    ):
        tags.setdefault(tag.story_id, {}).setdefault(tag.kind, set()).add(tag.value)

    sources = _sources_by_cluster(session, {story.cluster_id for story in stories})

    return [
        Candidate(
            story_id=story.id,
            genre=story.genre,  # type: ignore[arg-type]
            headline=story.headline,
            summary=story.summary,
            one_liner=story.one_liner,
            why_this_matters=story.why_this_matters,
            hedged=story.hedged,
            india_relevance=story.india_relevance,
            pool_rank=story.pool_rank,
            topic_tags=frozenset(tags.get(story.id, {}).get(TagKind.TOPIC, set())),
            entity_tags=frozenset(tags.get(story.id, {}).get(TagKind.ENTITY, set())),
            sources=sources.get(story.cluster_id, ()),
        )
        for story in stories
    ]


def _sources_by_cluster(
    session: Session, cluster_ids: set[uuid.UUID]
) -> dict[uuid.UUID, tuple[SourceLink, ...]]:
    """One link per source per cluster, named from config/sources.yaml."""
    if not cluster_ids:
        return {}

    names = {source.key: source.name for source in load_sources().sources}
    rows = session.execute(
        select(ClusterArticle.cluster_id, Source.key, Article.url)
        .join(Article, Article.id == ClusterArticle.article_id)
        .join(Source, Source.id == Article.source_id)
        .where(ClusterArticle.cluster_id.in_(list(cluster_ids)))
        .order_by(ClusterArticle.is_primary.desc(), Source.key)
    ).all()

    collected: dict[uuid.UUID, dict[str, SourceLink]] = {}
    for cluster_id, source_key, url in rows:
        seen = collected.setdefault(cluster_id, {})
        if source_key not in seen:
            seen[source_key] = SourceLink(name=names.get(source_key, source_key), url=url)

    return {cluster_id: tuple(links.values()) for cluster_id, links in collected.items()}

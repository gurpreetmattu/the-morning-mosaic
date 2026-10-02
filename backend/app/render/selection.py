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


def _article_key(url: str) -> str:
    """A source URL with the parts that vary between feeds of the same article removed."""
    return url.split("#", 1)[0].rstrip("/").lower()


def drop_duplicate_events(
    candidates: Sequence[Candidate], *, genre_order: Sequence[GenreKey]
) -> list[Candidate]:
    """Keep one story per event.

    Two stories that cite the same source article are the same event, whether the
    Writer produced them in one genre (clustering split it) or in two (Technology and
    AI both collect the same wire stories). Of each such group the best-ranked story
    survives; ties go to the genre that comes first in `genre_order`, then to the
    story id, so the choice never changes between runs or between readers.
    """
    parent: dict[uuid.UUID, uuid.UUID] = {c.story_id: c.story_id for c in candidates}

    def find(item: uuid.UUID) -> uuid.UUID:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    first_seen: dict[str, uuid.UUID] = {}
    for candidate in candidates:
        for source in candidate.sources:
            key = _article_key(source.url)
            if key in first_seen:
                parent[find(candidate.story_id)] = find(first_seen[key])
            else:
                first_seen[key] = candidate.story_id

    order = {genre: index for index, genre in enumerate(genre_order)}
    best: dict[uuid.UUID, Candidate] = {}
    for candidate in candidates:
        root = find(candidate.story_id)
        rank = (
            candidate.pool_rank,
            order.get(candidate.genre, len(order)),
            str(candidate.story_id),
        )
        current = best.get(root)
        if current is None or rank < (
            current.pool_rank,
            order.get(current.genre, len(order)),
            str(current.story_id),
        ):
            best[root] = candidate
    keep = {candidate.story_id for candidate in best.values()}
    return [candidate for candidate in candidates if candidate.story_id in keep]


def quiet_genres(reader: Reader, selected: Mapping[GenreKey, list[Candidate]]) -> list[GenreKey]:
    """The reader's genres that came up too thin to show, in the reader's order.

    CLAUDE.md: a section with fewer than the minimum stories "shows a short 'quiet
    news day' note instead". The email shows the note rather than dropping the genre.
    """
    return [genre for genre in reader.genres if genre not in selected]


def select_for_reader(
    candidates: Sequence[Candidate],
    reader: Reader,
    *,
    genres: GenresConfig | None = None,
) -> dict[GenreKey, list[Candidate]]:
    """Pick and order each subscribed genre's stories for one reader."""
    config = genres or load_genres()
    settings = config.by_key()
    chosen: dict[GenreKey, list[Candidate]] = {}
    candidates = drop_duplicate_events(candidates, genre_order=[g.key for g in config.genres])

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

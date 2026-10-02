"""Per-user selection: deterministic, and never generative."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from app.agents.schemas import (
    DraftSentence,
    GenreOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.config.loader import load_genres
from app.config.schemas import GenreKey
from app.db.persist import persist_genre
from app.db.seed import seed_sources
from app.models.enums import EditionPreference, SectionStatus
from app.render.selection import (
    Candidate,
    Reader,
    SourceLink,
    drop_duplicate_events,
    load_candidates,
    matches_keywords,
    quiet_genres,
    score,
    select_for_reader,
)
from app.sources.schemas import CollectedArticle, Passage

POOL_SIZE = load_genres().by_key()["india"].pool_size
EDITION_DATE = date(2026, 10, 5)
NOW = datetime(2026, 10, 5, 4, 15, tzinfo=UTC)


def stored_outcome() -> GenreOutcome:
    body = "The cabinet approved the eastern freight corridor on Tuesday, officials said."
    article = CollectedArticle(
        source_key="the-hindu",
        genre="india",
        url="https://example.test/persisted",
        title="Corridor",
        published_at=NOW,
        fetched_at=NOW,
        text=body,
        passages=[Passage(ordinal=1, text=body)],
        content_hash="hash-persisted",
    )
    return GenreOutcome(
        genre="india",
        status=SectionStatus.OK,
        stories=[
            VerifiedStory(
                story=WrittenStory(
                    headline=DraftSentence(
                        text="Corridor cleared by cabinet", passage_ids=["a1:p1"]
                    ),
                    summary=[DraftSentence(text="Ministers approved it.", passage_ids=["a1:p1"])],
                    topic_tags=["infrastructure"],
                    entity_tags=["cabinet"],
                ),
                articles=[article],
                pool_rank=1,
                attempts=1,
            )
        ],
    )


def candidate(
    rank: int,
    *,
    genre: GenreKey = "india",
    topics: set[str] | None = None,
    entities: set[str] | None = None,
    india: bool = False,
) -> Candidate:
    return Candidate(
        story_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{genre}-{rank}"),
        genre=genre,
        headline=f"Headline {rank}",
        summary="Summary.",
        one_liner=f"One liner {rank}",
        why_this_matters=None,
        hedged=False,
        india_relevance=india,
        pool_rank=rank,
        topic_tags=frozenset(topics or set()),
        entity_tags=frozenset(entities or set()),
    )


def reader(**overrides: object) -> Reader:
    base: dict[str, object] = {
        "id": uuid.uuid4(),
        "first_name": "Asha",
        "genres": ("india",),
    }
    return Reader(**(base | overrides))  # type: ignore[arg-type]


def headlines(chosen: dict[GenreKey, list[Candidate]], genre: GenreKey = "india") -> list[str]:
    return [c.headline for c in chosen.get(genre, [])]


# ------------------------------------------------------------ default order


def test_without_signals_the_pool_order_is_kept() -> None:
    pool = [candidate(3), candidate(1), candidate(2)]
    chosen = select_for_reader(pool, reader())

    assert headlines(chosen) == ["Headline 1", "Headline 2", "Headline 3"]


def test_a_section_is_capped_at_the_genre_maximum() -> None:
    pool = [candidate(i) for i in range(1, 11)]
    chosen = select_for_reader(pool, reader())

    assert len(chosen["india"]) == 6  # genres.yaml max_stories


def test_a_genre_with_too_few_stories_is_omitted() -> None:
    chosen = select_for_reader([candidate(1)], reader())
    assert "india" not in chosen


def test_only_subscribed_genres_are_selected() -> None:
    pool = [candidate(1), candidate(2), candidate(1, genre="sports"), candidate(2, genre="sports")]
    chosen = select_for_reader(pool, reader(genres=("sports",)))

    assert set(chosen) == {"sports"}


# --------------------------------------------------------------- keywords


def test_a_followed_keyword_lifts_a_low_ranked_story_to_the_top() -> None:
    """CLAUDE.md: keyword matches replace lower-ranked stories within the cap."""
    pool = [candidate(i) for i in range(1, 8)]
    pool.append(candidate(9, topics={"cricket"}))

    chosen = select_for_reader(pool, reader(keywords=frozenset({"cricket"})))
    assert headlines(chosen)[0] == "Headline 9"


def test_a_keyword_matches_a_word_inside_an_entity_tag() -> None:
    subject = candidate(5, entities={"Indian Space Research Organisation ISRO"})
    assert matches_keywords(subject, frozenset({"isro"}))


def test_a_keyword_matches_a_topic_tag_exactly() -> None:
    assert matches_keywords(candidate(1, topics={"markets"}), frozenset({"Markets"}))


def test_an_unrelated_keyword_does_not_match() -> None:
    subject = candidate(1, topics={"markets"}, entities={"Reserve Bank"})
    assert not matches_keywords(subject, frozenset({"badminton"}))


def test_no_keywords_means_no_match() -> None:
    assert not matches_keywords(candidate(1, topics={"markets"}), frozenset())


def test_a_keyword_only_applies_within_subscribed_genres() -> None:
    """The story is a match, but the reader does not take that genre."""
    pool = [candidate(1), candidate(2), candidate(1, genre="sports", topics={"cricket"})]
    chosen = select_for_reader(pool, reader(keywords=frozenset({"cricket"})))

    assert "sports" not in chosen
    assert len(chosen["india"]) == 2


# ------------------------------------------------------ learned preferences


def test_a_liked_topic_lifts_a_story() -> None:
    plain, liked = candidate(1), candidate(2, topics={"cricket"})
    subject = reader(topic_scores={("india", "cricket"): 5.0})

    assert score(liked, subject, pool_size=POOL_SIZE) > score(plain, subject, pool_size=POOL_SIZE)


def test_a_disliked_topic_pushes_a_story_down() -> None:
    plain, disliked = candidate(2), candidate(1, topics={"cricket"})
    subject = reader(topic_scores={("india", "cricket"): -5.0})

    assert score(disliked, subject, pool_size=POOL_SIZE) < score(
        plain, subject, pool_size=POOL_SIZE
    )


def test_preferences_are_scoped_to_their_genre() -> None:
    subject = reader(topic_scores={("sports", "cricket"): 5.0})
    india_story = candidate(1, topics={"cricket"})

    assert score(india_story, subject, pool_size=POOL_SIZE) == float(POOL_SIZE)


# ------------------------------------------------------ edition preference


def test_the_india_edition_lifts_india_relevant_stories() -> None:
    subject = reader(edition_preference=EditionPreference.INDIA)
    assert score(candidate(1, india=True), subject, pool_size=POOL_SIZE) > score(
        candidate(1), subject, pool_size=POOL_SIZE
    )


def test_the_global_edition_pushes_them_down_without_removing_them() -> None:
    subject = reader(edition_preference=EditionPreference.GLOBAL)
    indian = candidate(1, india=True)

    assert score(indian, subject, pool_size=POOL_SIZE) < score(
        candidate(1), subject, pool_size=POOL_SIZE
    )
    # A nudge, not a filter: a big Indian story still outranks a weak one.
    assert score(indian, subject, pool_size=POOL_SIZE) > score(
        candidate(8), subject, pool_size=POOL_SIZE
    )


def test_the_mixed_edition_is_neutral() -> None:
    subject = reader(edition_preference=EditionPreference.MIXED)
    assert score(candidate(1, india=True), subject, pool_size=POOL_SIZE) == score(
        candidate(1), subject, pool_size=POOL_SIZE
    )


# ------------------------------------------------------------ determinism


def test_the_same_reader_and_pool_always_give_the_same_order() -> None:
    pool = [candidate(i, topics={"markets"}) for i in range(1, 9)]
    subject = reader(keywords=frozenset({"markets"}))

    first = headlines(select_for_reader(pool, subject))
    for _ in range(5):
        assert headlines(select_for_reader(list(reversed(pool)), subject)) == first


@pytest.mark.parametrize("preference", list(EditionPreference))
def test_every_edition_preference_produces_a_usable_section(
    preference: EditionPreference,
) -> None:
    pool = [candidate(i, india=i % 2 == 0) for i in range(1, 9)]
    chosen = select_for_reader(pool, reader(edition_preference=preference))
    assert len(chosen["india"]) == 6


# ------------------------------------------------------- loading from the db


@pytest.mark.integration
def test_candidates_load_with_their_tags_and_source_links(session: Session) -> None:
    """The join from story to cluster to article to source is not obvious."""
    seed_sources(session)
    session.flush()
    persist_genre(session, edition_date=EDITION_DATE, outcome=stored_outcome())

    loaded = load_candidates(session, edition_date=EDITION_DATE, genres=["india"])

    assert len(loaded) == 1
    only = loaded[0]
    assert only.headline == "Corridor cleared by cabinet"
    assert only.topic_tags == frozenset({"infrastructure"})
    assert only.entity_tags == frozenset({"cabinet"})
    assert [source.name for source in only.sources] == ["The Hindu"]
    assert only.sources[0].url == "https://example.test/persisted"


@pytest.mark.integration
def test_no_stories_means_no_candidates(session: Session) -> None:
    assert load_candidates(session, edition_date=EDITION_DATE, genres=["india"]) == []
    assert load_candidates(session, edition_date=EDITION_DATE, genres=[]) == []


# ---------------------------------------------- one story per event, quiet genres


def with_sources(item: Candidate, *urls: str) -> Candidate:
    from dataclasses import replace

    return replace(item, sources=tuple(SourceLink(name="Wire", url=url) for url in urls))


def test_two_stories_citing_the_same_article_are_one_event_and_the_better_rank_survives() -> None:
    tech = with_sources(candidate(1, genre="technology"), "https://wire.test/a/openai")
    ai = with_sources(candidate(3, genre="ai"), "https://wire.test/a/openai/")  # trailing slash

    chosen = select_for_reader(
        [tech, ai, candidate(2, genre="technology"), candidate(1, genre="ai")],
        reader(genres=("technology", "ai")),
    )

    kept = {c.story_id for stories in chosen.values() for c in stories}
    assert tech.story_id in kept
    assert ai.story_id not in kept


def test_a_duplicate_inside_one_genre_is_dropped_too() -> None:
    first = with_sources(candidate(2, genre="technology"), "https://wire.test/a/x")
    second = with_sources(candidate(4, genre="technology"), "https://wire.test/a/x#top")

    chosen = select_for_reader(
        [first, second, candidate(1, genre="technology"), candidate(3, genre="technology")],
        reader(genres=("technology",)),
    )

    ids = {c.story_id for c in chosen["technology"]}
    assert first.story_id in ids
    assert second.story_id not in ids


def test_a_tie_goes_to_the_genre_that_comes_first_in_config_order() -> None:
    tech = with_sources(candidate(1, genre="technology"), "https://wire.test/a/y")
    ai = with_sources(candidate(1, genre="ai"), "https://wire.test/a/y")

    kept = drop_duplicate_events([ai, tech], genre_order=["technology", "ai"])

    assert [c.genre for c in kept] == ["technology"]


def test_the_choice_does_not_depend_on_the_order_candidates_arrive_in() -> None:
    a = with_sources(candidate(2, genre="india"), "https://wire.test/a/z")
    b = with_sources(candidate(2, genre="business"), "https://wire.test/a/z")
    order: list[GenreKey] = ["india", "business"]

    assert drop_duplicate_events([a, b], genre_order=order) == drop_duplicate_events(
        [b, a], genre_order=order
    )


def test_stories_that_merely_share_a_source_site_are_not_duplicates() -> None:
    one = with_sources(candidate(1), "https://wire.test/a/one")
    two = with_sources(candidate(2), "https://wire.test/a/two")

    assert len(drop_duplicate_events([one, two], genre_order=["india"])) == 2


def test_quiet_genres_are_the_followed_ones_that_were_too_thin() -> None:
    chosen = select_for_reader(
        [candidate(1, genre="ai"), candidate(2, genre="ai")],
        reader(genres=("india", "business", "ai")),
    )

    assert quiet_genres(reader(genres=("india", "business", "ai")), chosen) == ["india", "business"]

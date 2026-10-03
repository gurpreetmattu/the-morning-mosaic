"""Weekend edition content: pure selection logic, then the persist/load
round trip against a real database."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.schemas import DraftSentence, GenreOutcome, VerifiedStory, WrittenStory
from app.config.schemas import EditionsConfig
from app.db.persist import persist_genre
from app.db.seed import seed_sources
from app.models.content import WeekendFeature
from app.models.enums import SectionStatus, WeekendFeatureKind
from app.render.selection import Candidate, SourceLink
from app.render.weekend import (
    LongerRead,
    QuizQuestion,
    RecapItem,
    WeekendContent,
    build_longer_reads,
    build_quiz,
    build_weekly_recap,
    load_weekend_features,
    persist_weekend_features,
    week_dates_before,
)
from app.sources.schemas import CollectedArticle, Passage

SATURDAY = date(2026, 10, 10)
SUNDAY = date(2026, 10, 11)
MONDAY = date(2026, 10, 5)


def config(saturday: list[str] | None = None, sunday: list[str] | None = None) -> EditionsConfig:
    return EditionsConfig.model_validate(
        {
            "launch_date": "2026-10-01",
            "weekend": {
                "saturday_features": saturday or ["top-stories", "longer-reads", "quiz"],
                "sunday_features": sunday or ["top-stories", "weekly-recap", "quiz"],
            },
        }
    )


def candidate(
    rank: int,
    *,
    genre: str = "india",
    headline: str | None = None,
    one_liner: str | None = "One liner",
) -> Candidate:
    return Candidate(
        story_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{genre}-{rank}"),
        genre=genre,  # type: ignore[arg-type]
        headline=headline or f"Headline {genre} {rank}",
        summary="Summary.",
        one_liner=one_liner,
        why_this_matters=None,
        hedged=False,
        india_relevance=False,
        pool_rank=rank,
        topic_tags=frozenset(),
        entity_tags=frozenset(),
        sources=(SourceLink(name="The Hindu", url=f"https://example.test/{genre}-{rank}"),),
    )


# ------------------------------------------------------------- week_dates_before


def test_saturday_gets_monday_through_friday() -> None:
    assert week_dates_before(SATURDAY) == [
        date(2026, 10, 5),
        date(2026, 10, 6),
        date(2026, 10, 7),
        date(2026, 10, 8),
        date(2026, 10, 9),
    ]


def test_sunday_gets_monday_through_saturday() -> None:
    assert week_dates_before(SUNDAY) == [
        date(2026, 10, 5),
        date(2026, 10, 6),
        date(2026, 10, 7),
        date(2026, 10, 8),
        date(2026, 10, 9),
        date(2026, 10, 10),
    ]


def test_monday_has_no_days_before_it_in_its_own_week() -> None:
    assert week_dates_before(MONDAY) == []


# ------------------------------------------------------------- longer reads


def test_longer_reads_keeps_only_top_ranked_stories() -> None:
    pool = [candidate(1), candidate(3), candidate(4, genre="sports")]
    picked = build_longer_reads(pool)
    assert {r.headline for r in picked} == {candidate(1).headline, candidate(3).headline}


def test_longer_reads_caps_at_the_limit() -> None:
    pool = [candidate(1, genre=g) for g in ("india", "sports", "business", "technology", "ai")]
    pool += [candidate(1, genre="music")]
    assert len(build_longer_reads(pool)) == 6


def test_a_longer_read_carries_its_sources() -> None:
    picked = build_longer_reads([candidate(1)])
    assert isinstance(picked[0], LongerRead)
    assert picked[0].sources[0].name == "The Hindu"


# ------------------------------------------------------------- weekly recap


def test_the_recap_falls_back_to_no_one_liner_rather_than_inventing_one() -> None:
    picked = build_weekly_recap([candidate(1, one_liner=None)])
    assert isinstance(picked[0], RecapItem)
    assert picked[0].one_liner is None
    assert picked[0].headline


# ------------------------------------------------------------------- quiz


def significant_pool() -> list[Candidate]:
    return [
        candidate(1, genre="india"),
        candidate(1, genre="sports"),
        candidate(2, genre="business"),
        candidate(3, genre="technology"),
        candidate(1, genre="ai"),
    ]


def test_too_few_significant_stories_means_no_quiz() -> None:
    assert build_quiz([candidate(1)], edition_date=SATURDAY) == ()


def test_each_question_has_one_correct_answer_among_real_headlines() -> None:
    questions = build_quiz(significant_pool(), edition_date=SATURDAY)
    headlines = {c.headline for c in significant_pool()}
    for question in questions:
        assert len(question.options) == 4
        assert len(set(question.options)) == 4
        assert question.options[question.correct_index] in headlines
        assert all(option in headlines for option in question.options)


def test_the_quiz_is_deterministic_for_the_same_edition_date() -> None:
    first = build_quiz(significant_pool(), edition_date=SATURDAY)
    second = build_quiz(significant_pool(), edition_date=SATURDAY)
    assert first == second


def test_different_edition_dates_can_shuffle_differently() -> None:
    a = build_quiz(significant_pool(), edition_date=SATURDAY)
    b = build_quiz(significant_pool(), edition_date=SUNDAY)
    assert a != b


def test_a_question_answer_links_to_the_storys_own_source() -> None:
    questions = build_quiz(significant_pool(), edition_date=SATURDAY)
    for question in questions:
        assert question.source_url.startswith("https://example.test/")


# ------------------------------------------------------ WeekendContent truthiness


def test_an_empty_weekend_content_is_falsy() -> None:
    assert not WeekendContent()


def test_a_weekend_content_with_any_feature_is_truthy() -> None:
    assert WeekendContent(quiz=(QuizQuestion("Q", ("a", "b", "c", "d"), 0, "S", "https://x"),))


# ----------------------------------------------------------- persist / load


def article(tag: str, *, genre: str, edition_date: date) -> CollectedArticle:
    body = f"Officials confirmed the {tag} development on the record."
    at = datetime.combine(edition_date, time(12, 0), tzinfo=UTC)
    return CollectedArticle(
        source_key="the-hindu",
        genre=genre,  # type: ignore[arg-type]
        url=f"https://example.test/{tag}",
        title=f"Story {tag}",
        published_at=at,
        fetched_at=at,
        text=body,
        passages=[Passage(ordinal=1, text=body)],
        content_hash=f"hash-{tag}",
    )


def store(session: Session, tag: str, *, genre: str, edition_date: date, rank: int) -> None:
    persist_genre(
        session,
        edition_date=edition_date,
        outcome=GenreOutcome(
            genre=genre,  # type: ignore[arg-type]
            status=SectionStatus.OK,
            stories=[
                VerifiedStory(
                    story=WrittenStory(
                        headline=DraftSentence(text=f"Headline {tag}", passage_ids=["a1:p1"]),
                        summary=[DraftSentence(text="It happened.", passage_ids=["a1:p1"])],
                    ),
                    articles=[article(tag, genre=genre, edition_date=edition_date)],
                    pool_rank=rank,
                    attempts=1,
                )
            ],
        ),
    )


@pytest.fixture(autouse=True)
def _sources(session: Session) -> None:
    seed_sources(session)
    session.flush()


def _seed_the_week(session: Session) -> None:
    store(session, "mon", genre="india", edition_date=date(2026, 10, 5), rank=1)
    store(session, "tue", genre="sports", edition_date=date(2026, 10, 6), rank=1)
    store(session, "wed", genre="business", edition_date=date(2026, 10, 7), rank=2)
    store(session, "thu", genre="technology", edition_date=date(2026, 10, 8), rank=1)
    store(session, "fri", genre="ai", edition_date=date(2026, 10, 9), rank=3)


@pytest.mark.integration
def test_a_weekday_persists_nothing(session: Session) -> None:
    _seed_the_week(session)
    assert persist_weekend_features(session, edition_date=MONDAY, editions=config()) == ()
    assert session.scalar(select(WeekendFeature)) is None


@pytest.mark.integration
def test_saturday_builds_longer_reads_and_quiz_but_not_recap(session: Session) -> None:
    _seed_the_week(session)

    rows = persist_weekend_features(session, edition_date=SATURDAY, editions=config())

    kinds = {row.kind for row in rows}
    assert kinds == {WeekendFeatureKind.LONGER_READS, WeekendFeatureKind.QUIZ}


@pytest.mark.integration
def test_sunday_builds_recap_and_quiz_but_not_longer_reads(session: Session) -> None:
    _seed_the_week(session)

    rows = persist_weekend_features(session, edition_date=SUNDAY, editions=config())

    kinds = {row.kind for row in rows}
    assert kinds == {WeekendFeatureKind.WEEKLY_RECAP, WeekendFeatureKind.QUIZ}


@pytest.mark.integration
def test_sundays_recap_includes_saturdays_own_stories(session: Session) -> None:
    _seed_the_week(session)
    store(session, "sat", genre="music", edition_date=SATURDAY, rank=1)

    persist_weekend_features(session, edition_date=SUNDAY, editions=config())
    loaded = load_weekend_features(session, edition_date=SUNDAY)

    assert any(item.headline == "Headline sat" for item in loaded.weekly_recap)


@pytest.mark.integration
def test_rerunning_the_build_replaces_rather_than_duplicates(session: Session) -> None:
    _seed_the_week(session)

    persist_weekend_features(session, edition_date=SATURDAY, editions=config())
    persist_weekend_features(session, edition_date=SATURDAY, editions=config())

    rows = session.scalars(
        select(WeekendFeature).where(WeekendFeature.edition_date == SATURDAY)
    ).all()
    assert len(rows) == len({row.kind for row in rows})


@pytest.mark.integration
def test_loading_reconstructs_what_was_persisted(session: Session) -> None:
    _seed_the_week(session)
    persist_weekend_features(session, edition_date=SATURDAY, editions=config())

    loaded = load_weekend_features(session, edition_date=SATURDAY, editions=config())

    assert loaded.longer_reads
    first = loaded.longer_reads[0]
    assert isinstance(first, LongerRead)
    assert first.sources and first.sources[0].name == "The Hindu"
    assert loaded.quiz
    assert isinstance(loaded.quiz[0], QuizQuestion)


@pytest.mark.integration
def test_loading_a_date_with_no_weekend_features_is_empty(session: Session) -> None:
    assert load_weekend_features(session, edition_date=SATURDAY) == WeekendContent()


@pytest.mark.integration
def test_a_thin_week_with_no_stories_builds_nothing(session: Session) -> None:
    assert persist_weekend_features(session, edition_date=SATURDAY, editions=config()) == ()

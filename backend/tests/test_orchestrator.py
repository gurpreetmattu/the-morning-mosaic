"""Orchestrator: deadlines, failure isolation, and the quiet-day rule."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.agents.orchestrator import FAILED_NOTE, QUIET_DAY_NOTE, Orchestrator
from app.agents.schemas import (
    Corroboration,
    DraftSentence,
    PooledStory,
    StoryPool,
    VerificationOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.config.loader import load_editions, load_genres
from app.config.schemas import EditionsConfig, GenreKey
from app.models.enums import SectionStatus
from app.sources.schemas import CollectedArticle, CollectionResult, Passage

NOW = datetime(2026, 10, 5, 4, 15, tzinfo=UTC)  # a Monday
DEADLINE = NOW + timedelta(hours=1)
EDITION_DATE = date(2026, 10, 5)


def article(index: int) -> CollectedArticle:
    text = f"Passage body number {index} with enough words to be a citable passage."
    return CollectedArticle(
        source_key="wire",
        genre="india",
        url=f"https://wire.example/{index}",
        title=f"Story {index}",
        published_at=NOW,
        fetched_at=NOW,
        text=text,
        passages=[Passage(ordinal=1, text=text)],
        content_hash=f"h{index}",
    )


def pooled(index: int) -> PooledStory:
    return PooledStory(
        event_label=f"event {index}",
        articles=[article(index)],
        corroboration=Corroboration.PRIMARY_OFFICIAL,
        hedged=False,
        score=10.0 - index,
        rank=index + 1,
    )


def verified(index: int) -> VerifiedStory:
    return VerifiedStory(
        story=WrittenStory(
            headline=DraftSentence(text=f"Headline {index}", passage_ids=["a1:p1"]),
            summary=[DraftSentence(text=f"Summary {index}.", passage_ids=["a1:p1"])],
        ),
        attempts=1,
    )


class FakeCollector:
    def __init__(self, count: int = 4, raises: bool = False) -> None:
        self.count = count
        self.raises = raises

    def collect(self, genre: GenreKey, *, now: datetime | None = None) -> CollectionResult:
        if self.raises:
            raise RuntimeError("feed exploded")
        return CollectionResult(genre=genre, articles=[article(i) for i in range(self.count)])


class FakeRanker:
    def __init__(self, count: int = 4, raises: bool = False) -> None:
        self.count = count
        self.raises = raises

    def rank(self, collected: CollectionResult, *, now: datetime | None = None) -> StoryPool:
        if self.raises:
            raise RuntimeError("ranker exploded")
        return StoryPool(genre=collected.genre, stories=[pooled(i) for i in range(self.count)])


class FakeVerifier:
    """Verifies the first `succeed` candidates, abandons the rest."""

    def __init__(self, succeed: int = 99) -> None:
        self.succeed = succeed
        self.calls = 0

    def __call__(self, story: PooledStory, genre: GenreKey) -> VerificationOutcome:
        self.calls += 1
        if self.calls <= self.succeed:
            return VerificationOutcome(verified=verified(self.calls), attempts=1)
        return VerificationOutcome(verified=None, attempts=3, reason="unverifiable")


class Clock:
    """A clock the test moves by hand."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now


def orchestrator(
    *,
    collector: FakeCollector | None = None,
    ranker: FakeRanker | None = None,
    verify: FakeVerifier | None = None,
    clock: Clock | None = None,
    editions: EditionsConfig | None = None,
) -> Orchestrator:
    return Orchestrator(
        collector=collector or FakeCollector(),
        ranker=ranker or FakeRanker(),
        verify=verify or FakeVerifier(),
        genres=load_genres(),
        editions=editions or launch_on(date(2026, 10, 1)),
        max_workers=1,
        clock=clock or Clock(NOW),
    )


def launch_on(launch: date) -> EditionsConfig:
    payload = load_editions().model_dump()
    payload["launch_date"] = launch
    return EditionsConfig.model_validate(payload)


# --------------------------------------------------------------- one genre


def test_a_genre_with_enough_verified_stories_is_ok() -> None:
    outcome = orchestrator().build_genre("india", deadline=DEADLINE, now=NOW)

    assert outcome.status is SectionStatus.OK
    assert outcome.verified_count == 4
    assert outcome.collected == 4
    assert outcome.pooled == 4
    assert outcome.note is None


def test_fewer_than_two_verified_stories_is_a_quiet_day() -> None:
    outcome = orchestrator(verify=FakeVerifier(succeed=1)).build_genre(
        "india", deadline=DEADLINE, now=NOW
    )

    assert outcome.status is SectionStatus.QUIET_DAY
    assert outcome.stories == []
    assert outcome.note == QUIET_DAY_NOTE


def test_no_collected_articles_is_a_quiet_day_not_a_failure() -> None:
    outcome = orchestrator(collector=FakeCollector(count=0)).build_genre(
        "india", deadline=DEADLINE, now=NOW
    )
    assert outcome.status is SectionStatus.QUIET_DAY


def test_the_whole_pool_is_verified_not_just_the_six_a_section_shows() -> None:
    """Personalisation picks from the pool, so the pool must survive the build."""
    verifier = FakeVerifier()
    outcome = orchestrator(
        collector=FakeCollector(count=12), ranker=FakeRanker(count=12), verify=verifier
    ).build_genre("india", deadline=DEADLINE, now=NOW)

    assert outcome.verified_count == 10  # genres.yaml pool_size
    assert verifier.calls == 10


# ---------------------------------------------------------------- deadlines


def test_a_genre_started_after_the_deadline_fails_without_fetching() -> None:
    collector = FakeCollector()
    clock = Clock(DEADLINE + timedelta(minutes=1))
    outcome = orchestrator(collector=collector, clock=clock).build_genre(
        "india", deadline=DEADLINE, now=NOW
    )

    assert outcome.status is SectionStatus.FAILED
    assert outcome.deadline_hit is True
    assert outcome.collected == 0


def test_the_deadline_stops_verification_but_keeps_what_is_already_done() -> None:
    clock = Clock(NOW)

    class Ticking(FakeVerifier):
        def __call__(self, story: PooledStory, genre: GenreKey) -> VerificationOutcome:
            result = super().__call__(story, genre)
            if self.calls == 2:
                clock.now = DEADLINE  # the third candidate never starts
            return result

    outcome = orchestrator(verify=Ticking(), clock=clock).build_genre(
        "india", deadline=DEADLINE, now=NOW
    )

    assert outcome.status is SectionStatus.OK
    assert outcome.verified_count == 2
    assert outcome.deadline_hit is True


# ------------------------------------------------------------- isolation


def test_a_raising_collector_is_contained_by_the_build() -> None:
    build = orchestrator(collector=FakeCollector(raises=True)).build(
        edition_date=EDITION_DATE, deadline=DEADLINE, now=NOW
    )

    assert len(build.genres) == 10
    assert all(outcome.status is SectionStatus.FAILED for outcome in build.genres)
    assert build.genres[0].note == FAILED_NOTE
    assert build.failed is True


def test_a_raising_ranker_is_contained() -> None:
    build = orchestrator(ranker=FakeRanker(raises=True)).build(
        edition_date=EDITION_DATE, deadline=DEADLINE, genres=["india"], now=NOW
    )
    assert build.genres[0].status is SectionStatus.FAILED


def test_one_failing_genre_does_not_touch_the_others() -> None:
    class PickyCollector(FakeCollector):
        def collect(self, genre: GenreKey, *, now: datetime | None = None) -> CollectionResult:
            if genre == "politics":
                raise RuntimeError("only politics is broken")
            return super().collect(genre, now=now)

    build = orchestrator(collector=PickyCollector()).build(
        edition_date=EDITION_DATE,
        deadline=DEADLINE,
        genres=["india", "politics", "sports"],
        now=NOW,
    )

    statuses = {outcome.genre: outcome.status for outcome in build.genres}
    assert statuses["india"] is SectionStatus.OK
    assert statuses["politics"] is SectionStatus.FAILED
    assert statuses["sports"] is SectionStatus.OK
    assert build.failed is False


# ------------------------------------------------------------ edition facts


def test_the_edition_number_counts_days_since_launch() -> None:
    build = orchestrator(editions=launch_on(date(2026, 10, 1))).build(
        edition_date=date(2026, 10, 5), deadline=DEADLINE, genres=["india"], now=NOW
    )
    assert build.edition_number == 5


def test_launch_day_is_edition_one() -> None:
    subject = orchestrator(editions=launch_on(date(2026, 10, 5)))
    assert subject.edition_number(date(2026, 10, 5)) == 1


def test_a_date_before_launch_is_refused_rather_than_numbered_zero() -> None:
    subject = orchestrator(editions=launch_on(date(2026, 10, 5)))
    with pytest.raises(ValueError, match="precedes launch_date"):
        subject.edition_number(date(2026, 10, 1))


def test_a_special_edition_is_applied_from_the_calendar() -> None:
    build = orchestrator(editions=launch_on(date(2026, 1, 1))).build(
        edition_date=date(2026, 10, 2),  # Gandhi Jayanti
        deadline=DEADLINE,
        genres=["india"],
        now=NOW,
    )
    assert build.special_edition_key == "gandhi-jayanti-2026"


def test_an_ordinary_day_has_no_special_edition() -> None:
    build = orchestrator().build(
        edition_date=EDITION_DATE, deadline=DEADLINE, genres=["india"], now=NOW
    )
    assert build.special_edition_key is None


def test_saturday_and_sunday_are_weekend_editions() -> None:
    subject = orchestrator(editions=launch_on(date(2026, 1, 1)))
    weekday = subject.build(
        edition_date=date(2026, 10, 5), deadline=DEADLINE, genres=["india"], now=NOW
    )
    saturday = subject.build(
        edition_date=date(2026, 10, 3), deadline=DEADLINE, genres=["india"], now=NOW
    )
    assert weekday.is_weekend is False
    assert saturday.is_weekend is True


def test_every_genre_is_built_when_none_are_named() -> None:
    build = orchestrator().build(edition_date=EDITION_DATE, deadline=DEADLINE, now=NOW)
    assert len(build.genres) == 10
    assert len(build.usable_sections) == 10


def test_genres_can_run_in_parallel() -> None:
    subject = Orchestrator(
        collector=FakeCollector(),
        ranker=FakeRanker(),
        verify=FakeVerifier(),
        genres=load_genres(),
        editions=launch_on(date(2026, 10, 1)),
        max_workers=4,
        clock=Clock(NOW),
    )
    build = subject.build(edition_date=EDITION_DATE, deadline=DEADLINE, now=NOW)

    assert len(build.genres) == 10
    assert all(outcome.status is SectionStatus.OK for outcome in build.genres)

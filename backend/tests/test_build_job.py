"""The build job: the whole pipeline, against the real database."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.orchestrator import CollectorLike, Orchestrator, VerifyFn
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
from app.db.seed import seed_sources
from app.jobs.build import BUILD_DEADLINE_IST, BuildReport, deadline_for, run_build
from app.jobs.locking import job_lock, lock_key
from app.models.content import SentenceCitation, Story
from app.models.editions import Edition, EditionRevision, EditionSection
from app.models.enums import JobName, RunStatus, SectionStatus
from app.models.operations import PipelineRun
from app.render.sections import SectionRenderer
from app.sources.schemas import CollectedArticle, CollectionResult, Passage

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 5, 4, 15, tzinfo=UTC)
DEADLINE = NOW + timedelta(hours=1)
EDITION = date(2026, 10, 5)

BODY = "The cabinet approved the eastern freight corridor on Tuesday, officials said."


def article(index: int) -> CollectedArticle:
    return CollectedArticle(
        source_key="the-hindu",
        genre="india",
        url=f"https://example.test/story-{index}",
        title=f"Corridor story {index}",
        published_at=NOW,
        fetched_at=NOW,
        text=BODY,
        passages=[Passage(ordinal=1, text=BODY)],
        content_hash=f"hash-{index}",
    )


class FakeCollector:
    def __init__(self, count: int = 3) -> None:
        self.count = count

    def collect(self, genre: GenreKey, *, now: datetime | None = None) -> CollectionResult:
        return CollectionResult(genre=genre, articles=[article(i) for i in range(self.count)])


class FakeRanker:
    def rank(self, collected: CollectionResult, *, now: datetime | None = None) -> StoryPool:
        return StoryPool(
            genre=collected.genre,
            stories=[
                PooledStory(
                    event_label=f"event {index}",
                    articles=[item],
                    corroboration=Corroboration.PRIMARY_OFFICIAL,
                    hedged=False,
                    score=5.0,
                    rank=index + 1,
                )
                for index, item in enumerate(collected.articles)
            ],
        )


def verify_all(pooled: PooledStory, genre: GenreKey) -> VerificationOutcome:
    return VerificationOutcome(
        verified=VerifiedStory(
            story=WrittenStory(
                headline=DraftSentence(
                    text=f"Corridor cleared ({pooled.rank})", passage_ids=["a1:p1"]
                ),
                summary=[DraftSentence(text="Ministers approved the plan.", passage_ids=["a1:p1"])],
                topic_tags=["infrastructure"],
                model="test-model",
                prompt_version="writer-v1",
            ),
            articles=list(pooled.articles),
            pool_rank=pooled.rank,
            attempts=1,
        ),
        attempts=1,
    )


def verify_none(pooled: PooledStory, genre: GenreKey) -> VerificationOutcome:
    return VerificationOutcome(verified=None, attempts=3, reason="unverifiable")


def launch_on(launch: date) -> EditionsConfig:
    payload = load_editions().model_dump()
    payload["launch_date"] = launch
    return EditionsConfig.model_validate(payload)


def orchestrator(
    collector: CollectorLike | None = None, verify: VerifyFn = verify_all
) -> Orchestrator:
    return Orchestrator(
        collector=collector or FakeCollector(),
        ranker=FakeRanker(),
        verify=verify,
        genres=load_genres(),
        editions=launch_on(date(2026, 10, 1)),
        max_workers=1,
        clock=lambda: NOW,
    )


def build(
    session: Session,
    *,
    subject: Orchestrator | None = None,
    genres: list[GenreKey] | None = None,
) -> BuildReport:
    return run_build(
        session,
        edition_date=EDITION,
        deadline=DEADLINE,
        orchestrator=subject or orchestrator(),
        renderer=SectionRenderer(),
        genres=genres or ["india"],
        now=NOW,
    )


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def this_run(session: Session) -> PipelineRun | None:
    """The run this test created.

    Scoped by started_at rather than taking the only row: the database is also
    used by hand, so a real `python -m app.jobs.build` can leave committed runs
    behind.
    """
    return session.scalar(select(PipelineRun).where(PipelineRun.started_at == NOW))


@pytest.fixture(autouse=True)
def _sources(session: Session) -> None:
    seed_sources(session)
    session.flush()


# ------------------------------------------------------------- happy path


def test_a_successful_build_publishes_revision_one(session: Session) -> None:
    report = build(session)

    assert report.succeeded
    assert report.published_revision == 1
    assert report.sections == {"india": "ok"}
    assert report.stories_persisted == 3

    edition = session.scalar(select(Edition))
    assert edition is not None
    assert edition.edition_number == 5  # 2026-10-05, launched 2026-10-01


def test_the_published_section_carries_the_rendered_story(session: Session) -> None:
    build(session)

    stored = session.scalar(select(EditionSection))
    assert stored is not None
    assert stored.status is SectionStatus.OK
    assert "Corridor cleared" in (stored.html or "")
    assert "Corridor cleared" in (stored.plain_text or "")
    assert stored.story_count == 3


def test_the_audit_trail_is_written_alongside_the_revision(session: Session) -> None:
    build(session)

    assert count(session, Story) == 3
    # Every published sentence cites a real passage.
    assert count(session, SentenceCitation) == 6  # 3 stories x (headline + summary)


def test_the_run_is_recorded_as_succeeded(session: Session) -> None:
    build(session)

    run = this_run(session)
    assert run is not None
    assert run.job is JobName.BUILD
    assert run.status is RunStatus.SUCCEEDED
    assert run.finished_at is not None
    assert run.detail is not None
    assert run.detail["published_revision"] == 1


# ------------------------------------------------------------- failure


def test_a_build_with_nothing_verifiable_publishes_nothing(session: Session) -> None:
    report = build(session, subject=orchestrator(verify=verify_none))

    assert not report.succeeded
    assert report.error is not None
    assert count(session, Edition) == 0
    assert count(session, EditionRevision) == 0


def test_a_failed_build_is_recorded_as_failed(session: Session) -> None:
    build(session, subject=orchestrator(verify=verify_none))

    run = this_run(session)
    assert run is not None
    assert run.status is RunStatus.FAILED


def test_a_quiet_genre_alongside_a_good_one_still_publishes(session: Session) -> None:
    class OnlyIndia(FakeCollector):
        def collect(self, genre: GenreKey, *, now: datetime | None = None) -> CollectionResult:
            if genre != "india":
                return CollectionResult(genre=genre, articles=[])
            return super().collect(genre, now=now)

    report = build(
        session,
        subject=orchestrator(collector=OnlyIndia()),
        genres=["india", "politics"],
    )

    assert report.succeeded
    assert report.sections == {"india": "ok", "politics": "quiet_day"}


# ------------------------------------------------------------- deadline


def test_the_deadline_is_an_ist_wall_clock_time() -> None:
    """05:30 IST is 00:00 UTC the same day."""
    assert deadline_for(date(2026, 10, 5)) == datetime(2026, 10, 5, 0, 0, tzinfo=UTC)
    assert time(5, 30) == BUILD_DEADLINE_IST


def test_a_deadline_miss_is_recorded_without_losing_the_edition(
    session: Session,
) -> None:
    clock_now = [NOW]
    calls = [0]

    def slow_verify(pooled: PooledStory, genre: GenreKey) -> VerificationOutcome:
        calls[0] += 1
        if calls[0] == 2:
            # The clock crosses the deadline; the third candidate never starts.
            clock_now[0] = DEADLINE
        return verify_all(pooled, genre)

    subject = Orchestrator(
        collector=FakeCollector(),
        ranker=FakeRanker(),
        verify=slow_verify,
        genres=load_genres(),
        editions=launch_on(date(2026, 10, 1)),
        max_workers=1,
        clock=lambda: clock_now[0],
    )
    report = build(session, subject=subject)

    assert report.deadline_missed is True
    assert report.succeeded  # two stories verified is enough to publish
    run = this_run(session)
    assert run is not None
    assert run.status is RunStatus.DEADLINE_MISSED


# --------------------------------------------------------------- locking


def test_the_lock_key_is_stable_and_fits_a_signed_64_bit_int() -> None:
    key = lock_key("build")
    assert key == lock_key("build")
    assert lock_key("build") != lock_key("delivery")
    assert -(2**63) <= key < 2**63


def test_a_second_holder_cannot_take_the_same_job_lock(engine: Engine) -> None:
    """A manual rerun during the scheduled run must not publish twice."""
    factory = sessionmaker(bind=engine)
    with job_lock("test-build-guard", session_factory=factory) as first:
        assert first is True
        with job_lock("test-build-guard", session_factory=factory) as second:
            assert second is False


def test_the_lock_is_released_when_the_block_exits(engine: Engine) -> None:
    factory = sessionmaker(bind=engine)
    with job_lock("test-build-release", session_factory=factory) as first:
        assert first is True
    with job_lock("test-build-release", session_factory=factory) as again:
        assert again is True

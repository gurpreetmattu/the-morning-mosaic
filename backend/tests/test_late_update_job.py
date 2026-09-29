"""Late update: append, never mutate; and miss the deadline, change nothing."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.orchestrator import CollectorLike, Orchestrator, VerifyFn
from app.agents.schemas import (
    Corroboration,
    DraftSentence,
    EditionBuild,
    GenreOutcome,
    PooledStory,
    StoryPool,
    VerificationOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.config.loader import load_editions, load_genres
from app.config.schemas import EditionsConfig, GenreKey
from app.db.persist import persist_genre, persist_new_stories
from app.db.publish import publish_revision
from app.db.seed import seed_sources
from app.jobs.late_update import LateUpdateReport, run_late_update
from app.models.content import Story
from app.models.editions import EditionRevision, EditionSection
from app.models.enums import RevisionReason, RunStatus, SectionStatus
from app.models.operations import PipelineRun
from app.render.sections import RenderedSection, SectionRenderer
from app.sources.schemas import CollectedArticle, CollectionResult, Passage

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 5, 0, 5, tzinfo=UTC)  # 05:35 IST
DEADLINE = NOW + timedelta(minutes=20)
EDITION = date(2026, 10, 5)

BODY = "The cabinet approved the eastern freight corridor on Tuesday, officials said."


def article(tag: str) -> CollectedArticle:
    return CollectedArticle(
        source_key="the-hindu",
        genre="india",
        url=f"https://example.test/{tag}",
        title=f"Story {tag}",
        published_at=NOW,
        fetched_at=NOW,
        text=BODY,
        passages=[Passage(ordinal=1, text=BODY)],
        content_hash=f"hash-{tag}",
    )


def verified(tag: str, rank: int = 1) -> VerifiedStory:
    return VerifiedStory(
        story=WrittenStory(
            headline=DraftSentence(text=f"Headline {tag}", passage_ids=["a1:p1"]),
            summary=[DraftSentence(text="Ministers approved.", passage_ids=["a1:p1"])],
            one_liner=DraftSentence(text=f"Line {tag}", passage_ids=["a1:p1"]),
        ),
        articles=[article(tag)],
        pool_rank=rank,
        attempts=1,
    )


def outcome(*tags: str, genre: GenreKey = "india") -> GenreOutcome:
    return GenreOutcome(
        genre=genre,
        status=SectionStatus.OK,
        stories=[verified(tag, index + 1) for index, tag in enumerate(tags)],
    )


class FakeCollector:
    def __init__(self, tags: tuple[str, ...]) -> None:
        self.tags = tags

    def collect(self, genre: GenreKey, *, now: datetime | None = None) -> CollectionResult:
        return CollectionResult(genre=genre, articles=[article(tag) for tag in self.tags])


class FakeRanker:
    def rank(self, collected: CollectionResult, *, now: datetime | None = None) -> StoryPool:
        return StoryPool(
            genre=collected.genre,
            stories=[
                PooledStory(
                    event_label=item.url,
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
    tag = pooled.articles[0].url.rsplit("/", 1)[-1]
    return VerificationOutcome(verified=verified(tag, pooled.rank), attempts=1)


def launch_on(launch: date) -> EditionsConfig:
    payload = load_editions().model_dump()
    payload["launch_date"] = launch
    return EditionsConfig.model_validate(payload)


def orchestrator(tags: tuple[str, ...], verify: VerifyFn = verify_all) -> Orchestrator:
    collector: CollectorLike = FakeCollector(tags)
    return Orchestrator(
        collector=collector,
        ranker=FakeRanker(),
        verify=verify,
        genres=load_genres(),
        editions=launch_on(date(2026, 10, 1)),
        max_workers=1,
        clock=lambda: NOW,
    )


def first_revision(session: Session, *tags: str) -> None:
    """The morning build: stories persisted and revision 1 published."""
    persist_genre(session, edition_date=EDITION, outcome=outcome(*tags))
    publish_revision(
        session,
        build=EditionBuild(edition_date=EDITION, edition_number=5, genres=[]),
        sections={
            "india": RenderedSection(
                genre="india",
                status=SectionStatus.OK,
                html="<p>original india</p>",
                plain_text="original india",
                story_count=len(tags),
            ),
            "sports": RenderedSection(
                genre="sports",
                status=SectionStatus.OK,
                html="<p>original sports</p>",
                plain_text="original sports",
                story_count=2,
            ),
        },
        published_at=NOW,
    )


@pytest.fixture(autouse=True)
def _sources(session: Session) -> None:
    seed_sources(session)
    session.flush()


def late_update(session: Session, tags: tuple[str, ...], **overrides: object) -> LateUpdateReport:
    kwargs: dict[str, object] = {
        "edition_date": EDITION,
        "deadline": DEADLINE,
        "orchestrator": orchestrator(tags),
        "renderer": SectionRenderer(),
        "genres": ["india"],
        "now": NOW,
        "clock": lambda: NOW,
    }
    kwargs.update(overrides)
    return run_late_update(session, **kwargs)  # type: ignore[arg-type]


def sections_of(session: Session, revision: EditionRevision) -> dict[str, EditionSection]:
    return {
        row.genre: row
        for row in session.scalars(
            select(EditionSection).where(EditionSection.revision_id == revision.id)
        )
    }


# ------------------------------------------------------- appending, not editing


def test_a_new_story_publishes_a_second_revision(session: Session) -> None:
    first_revision(session, "a", "b")

    report = late_update(session, ("a", "b", "c"))

    assert report.published_revision == 2
    assert report.new_stories == 1
    assert report.changed == ["india"]


def test_the_earlier_revision_is_left_exactly_as_it_was(session: Session) -> None:
    """Readers already received it; mutating it would rewrite their morning."""
    first_revision(session, "a", "b")
    original = session.scalars(select(EditionRevision)).one()
    original_html = sections_of(session, original)["india"].html

    late_update(session, ("a", "b", "c"))

    assert sections_of(session, original)["india"].html == original_html
    assert original.reason is RevisionReason.BUILD


def test_the_new_revision_holds_old_and_new_stories(session: Session) -> None:
    first_revision(session, "a", "b")
    late_update(session, ("a", "b", "c"))

    newest = session.scalars(
        select(EditionRevision).order_by(EditionRevision.revision.desc())
    ).first()
    assert newest is not None
    india = sections_of(session, newest)["india"]

    for tag in ("a", "b", "c"):
        assert f"Headline {tag}" in (india.html or "")
    assert india.story_count == 3


def test_existing_stories_are_not_replaced(session: Session) -> None:
    first_revision(session, "a", "b")
    before = {story.id for story in session.scalars(select(Story))}

    late_update(session, ("a", "b", "c"))

    after = {story.id for story in session.scalars(select(Story))}
    assert before < after  # strictly grown
    assert len(after) == 3


def test_an_unchanged_section_is_carried_forward_byte_for_byte(session: Session) -> None:
    first_revision(session, "a", "b")

    report = late_update(session, ("a", "b", "c"))

    newest = session.scalars(
        select(EditionRevision).order_by(EditionRevision.revision.desc())
    ).first()
    assert newest is not None
    assert sections_of(session, newest)["sports"].html == "<p>original sports</p>"
    assert report.carried_forward == ["sports"]


def test_the_revision_is_marked_as_a_late_update(session: Session) -> None:
    first_revision(session, "a", "b")
    late_update(session, ("a", "b", "c"))

    newest = session.scalars(
        select(EditionRevision).order_by(EditionRevision.revision.desc())
    ).first()
    assert newest is not None
    assert newest.reason is RevisionReason.LATE_UPDATE


def test_revisions_share_the_edition_number(session: Session) -> None:
    first_revision(session, "a", "b")
    late_update(session, ("a", "b", "c"))

    assert session.scalar(select(func.count()).select_from(EditionRevision)) == 2


# -------------------------------------------------------------- no change


def test_nothing_new_publishes_nothing(session: Session) -> None:
    first_revision(session, "a", "b")

    report = late_update(session, ("a", "b"))

    assert not report.published
    assert "nothing new" in (report.reason or "")
    assert session.scalar(select(func.count()).select_from(EditionRevision)) == 1


def test_a_story_already_stored_is_not_appended_twice(session: Session) -> None:
    persist_genre(session, edition_date=EDITION, outcome=outcome("a", "b"))
    added = persist_new_stories(session, edition_date=EDITION, outcome=outcome("a", "b"))
    assert added == []


def test_only_the_genuinely_new_story_is_appended(session: Session) -> None:
    persist_genre(session, edition_date=EDITION, outcome=outcome("a"))
    added = persist_new_stories(session, edition_date=EDITION, outcome=outcome("a", "b"))

    assert len(added) == 1
    assert added[0].headline == "Headline b"
    # Appended after the existing pool, not renumbered over it.
    assert added[0].pool_rank == 2


def test_a_reissue_under_a_fresh_url_is_still_recognised_by_content(session: Session) -> None:
    """A publisher can reissue the same story under a new URL; the dedup key
    is content hash, not URL, so it is not appended a second time."""
    persist_genre(session, edition_date=EDITION, outcome=outcome("a"))

    reissued = article("a").model_copy(update={"url": "https://example.test/a-reissued"})
    reissued_outcome = GenreOutcome(
        genre="india",
        status=SectionStatus.OK,
        stories=[
            VerifiedStory(
                story=WrittenStory(
                    headline=DraftSentence(text="Headline a", passage_ids=["a1:p1"]),
                    summary=[DraftSentence(text="Ministers approved.", passage_ids=["a1:p1"])],
                    one_liner=DraftSentence(text="Line a", passage_ids=["a1:p1"]),
                ),
                articles=[reissued],
                pool_rank=1,
                attempts=1,
            )
        ],
    )

    added = persist_new_stories(session, edition_date=EDITION, outcome=reissued_outcome)

    assert added == []


# --------------------------------------------------------------- guardrails


def test_it_refuses_to_publish_the_first_revision(session: Session) -> None:
    """A failed build is the failure-notice path's problem, not this job's."""
    report = late_update(session, ("a", "b"))

    assert not report.published
    assert "no published revision" in (report.reason or "")
    assert session.scalar(select(func.count()).select_from(EditionRevision)) == 0

    run = session.scalar(select(PipelineRun).where(PipelineRun.started_at == NOW))
    assert run is not None
    assert run.status is RunStatus.FAILED


def test_missing_the_deadline_changes_nothing(session: Session) -> None:
    first_revision(session, "a", "b")

    report = late_update(session, ("a", "b", "c"), clock=lambda: DEADLINE + timedelta(minutes=1))

    assert not report.published
    assert "deadline passed" in (report.reason or "")
    # Neither the new story nor a new revision survives.
    assert session.scalar(select(func.count()).select_from(EditionRevision)) == 1
    assert session.scalar(select(func.count()).select_from(Story)) == 2


def test_a_deadline_miss_is_recorded_as_such(session: Session) -> None:
    first_revision(session, "a", "b")
    late_update(session, ("a", "b", "c"), clock=lambda: DEADLINE + timedelta(minutes=1))

    run = session.scalar(select(PipelineRun).where(PipelineRun.started_at == NOW))
    assert run is not None
    assert run.status is RunStatus.DEADLINE_MISSED


def test_a_deadline_miss_logs_the_greppable_alert_message(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """infra/monitoring.tf's log-based metric matches on this literal text —
    see app/jobs/build.py's own deadline-miss log for the shared convention."""
    first_revision(session, "a", "b")

    with caplog.at_level(logging.WARNING):
        late_update(session, ("a", "b", "c"), clock=lambda: DEADLINE + timedelta(minutes=1))

    assert "build_deadline_missed" in caplog.text

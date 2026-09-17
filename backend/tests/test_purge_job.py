"""Raw-article purge: only stale raw text is cleared, nothing else."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.schemas import (
    DraftSentence,
    GenreOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.db.persist import persist_genre
from app.db.seed import seed_sources
from app.jobs.purge import DEFAULT_RETENTION_DAYS, run_purge
from app.models.content import Article
from app.models.enums import RunStatus, SectionStatus
from app.models.operations import PipelineRun
from app.sources.schemas import CollectedArticle, Passage

pytestmark = pytest.mark.integration

EDITION = date(2026, 10, 5)
NOW = datetime(2026, 10, 5, 21, 30, tzinfo=UTC)  # 03:00 IST on the 6th

BODY = "The cabinet approved the eastern freight corridor on Tuesday, officials said."


def article(tag: str, *, fetched_at: datetime) -> CollectedArticle:
    return CollectedArticle(
        source_key="the-hindu",
        genre="india",
        url=f"https://example.test/{tag}",
        title=f"Story {tag}",
        published_at=fetched_at,
        fetched_at=fetched_at,
        text=BODY,
        passages=[Passage(ordinal=1, text=BODY)],
        content_hash=f"hash-{tag}",
    )


def store(session: Session, tag: str, *, fetched_at: datetime) -> None:
    persist_genre(
        session,
        edition_date=EDITION,
        outcome=GenreOutcome(
            genre="india",
            status=SectionStatus.OK,
            stories=[
                VerifiedStory(
                    story=WrittenStory(
                        headline=DraftSentence(text=f"Headline {tag}", passage_ids=["a1:p1"]),
                        summary=[
                            DraftSentence(text="Ministers approved.", passage_ids=["a1:p1"])
                        ],
                    ),
                    articles=[article(tag, fetched_at=fetched_at)],
                    pool_rank=1,
                    attempts=1,
                )
            ],
        ),
    )


@pytest.fixture(autouse=True)
def _sources(session: Session) -> None:
    seed_sources(session)
    session.flush()


def by_tag(session: Session, tag: str) -> Article:
    row = session.scalar(select(Article).where(Article.url == f"https://example.test/{tag}"))
    assert row is not None
    return row


def test_raw_text_older_than_the_window_is_cleared(session: Session) -> None:
    store(session, "old", fetched_at=NOW - timedelta(days=DEFAULT_RETENTION_DAYS + 1))

    report = run_purge(session, now=NOW)

    assert report.purged == 1
    row = by_tag(session, "old")
    assert row.raw_text is None
    assert row.raw_text_purged_at == NOW


def test_raw_text_inside_the_window_is_left_alone(session: Session) -> None:
    store(session, "fresh", fetched_at=NOW - timedelta(days=1))

    report = run_purge(session, now=NOW)

    assert report.purged == 0
    row = by_tag(session, "fresh")
    assert row.raw_text is not None
    assert row.raw_text_purged_at is None


def test_an_article_right_at_the_boundary_is_kept(session: Session) -> None:
    """Exactly `retention_days` old has not yet exceeded the window."""
    store(session, "boundary", fetched_at=NOW - timedelta(days=DEFAULT_RETENTION_DAYS))

    run_purge(session, now=NOW)

    row = by_tag(session, "boundary")
    assert row.raw_text is not None


def test_an_already_purged_article_is_not_touched_again(session: Session) -> None:
    store(session, "old", fetched_at=NOW - timedelta(days=DEFAULT_RETENTION_DAYS + 1))
    first = run_purge(session, now=NOW)
    assert first.purged == 1

    second = run_purge(session, now=NOW + timedelta(days=1))

    assert second.purged == 0


def test_a_custom_retention_window_is_honoured(session: Session) -> None:
    store(session, "recent", fetched_at=NOW - timedelta(days=5))

    report = run_purge(session, now=NOW, retention_days=3)

    assert report.purged == 1


def test_the_run_is_recorded(session: Session) -> None:
    store(session, "old", fetched_at=NOW - timedelta(days=DEFAULT_RETENTION_DAYS + 1))

    run_purge(session, now=NOW)

    run = session.scalar(select(PipelineRun).where(PipelineRun.started_at == NOW))
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED
    assert run.detail == {"purged": 1, "retention_days": DEFAULT_RETENTION_DAYS}

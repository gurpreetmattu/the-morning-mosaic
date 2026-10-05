"""`fail_run` must record a crashed run, and only a run that is still running."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from app.jobs.runs import fail_run
from app.models.enums import JobName, RunStatus
from app.models.operations import PipelineRun


def make_run(session: Session, status: RunStatus = RunStatus.RUNNING) -> PipelineRun:
    run = PipelineRun(
        id=uuid.uuid4(),
        job=JobName.LATE_UPDATE,
        edition_date=date(2026, 10, 5),
        status=status,
        started_at=datetime(2026, 10, 5, 0, 5, tzinfo=UTC),
        deadline_at=datetime(2026, 10, 5, 0, 25, tzinfo=UTC),
    )
    session.add(run)
    session.flush()
    return run


@pytest.mark.integration
def test_a_crashed_run_is_marked_failed_with_the_error(session: Session) -> None:
    run = make_run(session)

    updated = fail_run(session, run.id, RuntimeError("terminating connection due to idle timeout"))

    assert updated is True
    assert run.status is RunStatus.FAILED
    assert run.finished_at is not None
    assert run.detail is not None
    assert "RuntimeError: terminating connection" in run.detail["error"]


@pytest.mark.integration
def test_a_run_that_already_finished_is_never_rewritten(session: Session) -> None:
    run = make_run(session, RunStatus.SUCCEEDED)

    assert fail_run(session, run.id, RuntimeError("late noise")) is False
    assert run.status is RunStatus.SUCCEEDED


@pytest.mark.integration
def test_an_unknown_run_id_is_ignored_not_raised(session: Session) -> None:
    assert fail_run(session, uuid.uuid4(), RuntimeError("x")) is False


@pytest.mark.integration
def test_existing_detail_is_kept_when_the_error_is_added(session: Session) -> None:
    run = make_run(session)
    run.detail = {"sections": {"india": "ok"}}
    session.flush()

    fail_run(session, run.id, ValueError("boom"))

    assert run.detail is not None
    assert run.detail["sections"] == {"india": "ok"}
    assert "boom" in run.detail["error"]

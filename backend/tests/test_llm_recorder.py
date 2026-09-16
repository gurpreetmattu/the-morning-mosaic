"""DatabaseCallRecorder: writes llm_calls rows via its own session.

The real default (`session_scope`) opens a genuinely separate connection —
deliberately, so usage is recorded even when the caller's own transaction
later rolls back (see the module docstring). That means it can't share the
test fixture's own transaction, so these tests inject a fake session
factory that hands back the fixture's `session` inside a no-op context
manager, and read the row back through that same session.
"""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.recorder import DatabaseCallRecorder
from app.models.enums import CallStatus, JobName, RunStatus
from app.models.operations import LlmCall, PipelineRun

NOW = datetime(2026, 9, 17, 4, 15, tzinfo=UTC)

pytestmark = pytest.mark.integration


def recorder(session: Session, *, pipeline_run_id: uuid.UUID | None = None) -> DatabaseCallRecorder:
    return DatabaseCallRecorder(
        pipeline_run_id=pipeline_run_id,
        session_factory=lambda: nullcontext(session),
    )


def test_a_successful_call_is_recorded(session: Session) -> None:
    recorder(session).record(
        agent="writer",
        model="test-model",
        provider="test-provider",
        prompt_version="writer_v1",
        prompt_tokens=100,
        completion_tokens=50,
        latency_ms=250,
        status="ok",
        error=None,
    )

    row = session.scalar(select(LlmCall))
    assert row is not None
    assert row.agent == "writer"
    assert row.model == "test-model"
    assert row.status is CallStatus.OK
    assert row.prompt_tokens == 100
    assert row.error is None


def test_a_failed_call_is_recorded_too(session: Session) -> None:
    recorder(session).record(
        agent="ranker",
        model="test-model",
        provider="test-provider",
        prompt_version=None,
        prompt_tokens=None,
        completion_tokens=None,
        latency_ms=10,
        status="error",
        error="timeout",
    )

    row = session.scalar(select(LlmCall))
    assert row is not None
    assert row.status is CallStatus.ERROR
    assert row.error == "timeout"


def test_the_pipeline_run_id_is_attached_when_given(session: Session) -> None:
    run = PipelineRun(job=JobName.BUILD, status=RunStatus.RUNNING, started_at=NOW)
    session.add(run)
    session.flush()
    run_id = run.id

    recorder(session, pipeline_run_id=run_id).record(
        agent="writer",
        model="test-model",
        provider="test-provider",
        prompt_version="writer_v1",
        prompt_tokens=1,
        completion_tokens=1,
        latency_ms=1,
        status="ok",
        error=None,
    )

    row = session.scalar(select(LlmCall))
    assert row is not None
    assert row.pipeline_run_id == run_id


def test_no_pipeline_run_id_leaves_it_null(session: Session) -> None:
    recorder(session).record(
        agent="writer",
        model="test-model",
        provider="test-provider",
        prompt_version="writer_v1",
        prompt_tokens=1,
        completion_tokens=1,
        latency_ms=1,
        status="ok",
        error=None,
    )

    row = session.scalar(select(LlmCall))
    assert row is not None
    assert row.pipeline_run_id is None

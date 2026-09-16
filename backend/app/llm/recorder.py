"""Persist LLM usage.

Each call opens its own short transaction rather than sharing the caller's:
LLM calls happen before a build's write phase begins (see app/jobs/build.py's
module docstring), and usage must still be recorded even when the build
itself fails and its own session rolls back.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from app.db.engine import session_scope
from app.models.enums import CallStatus
from app.models.operations import LlmCall


class DatabaseCallRecorder:
    """Writes one llm_calls row per attempt, including failed ones."""

    def __init__(
        self,
        pipeline_run_id: uuid.UUID | None = None,
        session_factory: Callable[[], AbstractContextManager[Session]] = session_scope,
    ) -> None:
        self._pipeline_run_id = pipeline_run_id
        self._session_factory = session_factory

    def record(
        self,
        *,
        agent: str,
        model: str,
        provider: str,
        prompt_version: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        latency_ms: int,
        status: str,
        error: str | None,
    ) -> None:
        with self._session_factory() as session:
            session.add(
                LlmCall(
                    pipeline_run_id=self._pipeline_run_id,
                    agent=agent,
                    model=model,
                    provider=provider,
                    prompt_version=prompt_version,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency_ms,
                    status=CallStatus(status),
                    error=error,
                )
            )

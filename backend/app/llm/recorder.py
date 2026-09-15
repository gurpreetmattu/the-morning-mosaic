"""Persist LLM usage.

Kept out of client.py so the client itself needs no database, which is what
lets the routing and retry tests run without one.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.enums import CallStatus
from app.models.operations import LlmCall


class DatabaseCallRecorder:
    """Writes one llm_calls row per attempt, including failed ones."""

    def __init__(self, session: Session, pipeline_run_id: uuid.UUID | None = None) -> None:
        self._session = session
        self._pipeline_run_id = pipeline_run_id

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
        self._session.add(
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

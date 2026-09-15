"""Operational records: job runs, LLM usage, and held notice batches."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    CreatedAt,
    EditionDate,
    Instant,
    OptionalInstant,
    UuidPk,
    pg_enum,
)
from app.models.enums import CallStatus, JobName, NoticeBatchStatus, RunStatus


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[UuidPk]
    job: Mapped[JobName] = mapped_column(pg_enum(JobName, "job_name"), nullable=False)
    edition_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[RunStatus] = mapped_column(
        pg_enum(RunStatus, "run_status"), nullable=False, default=RunStatus.RUNNING
    )
    started_at: Mapped[Instant]
    finished_at: Mapped[OptionalInstant]
    deadline_at: Mapped[OptionalInstant]
    detail: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    created_at: Mapped[CreatedAt]

    __table_args__ = (Index("ix_pipeline_runs_job_edition_date", "job", "edition_date"),)


class LlmCall(Base):
    """One request to the gateway. No personal data ever reaches an LLM, so
    nothing here may contain subscriber information."""

    __tablename__ = "llm_calls"

    id: Mapped[UuidPk]
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True
    )
    agent: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[CallStatus] = mapped_column(pg_enum(CallStatus, "call_status"), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[CreatedAt]

    __table_args__ = (Index("ix_llm_calls_agent_created_at", "agent", "created_at"),)


class NoticeBatch(Base):
    """A day's failure notices, held for approval when the count looks abnormal.

    A held batch expires unsent at 12:00 IST: a late apology is worse than none.
    """

    __tablename__ = "notice_batches"

    id: Mapped[UuidPk]
    edition_date: Mapped[EditionDate] = mapped_column(unique=True)
    status: Mapped[NoticeBatchStatus] = mapped_column(
        pg_enum(NoticeBatchStatus, "notice_batch_status"), nullable=False
    )
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[Instant]
    decided_at: Mapped[OptionalInstant]
    decided_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[CreatedAt]

    __table_args__ = (CheckConstraint("recipient_count >= 0", name="recipient_count_non_negative"),)


__all__ = ["LlmCall", "NoticeBatch", "PipelineRun"]

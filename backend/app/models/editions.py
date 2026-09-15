"""Editions, their immutable revisions, and per-user delivery records."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    CreatedAt,
    EditionDate,
    GenreKeyColumn,
    Instant,
    OptionalInstant,
    UuidPk,
    genre_check,
    pg_enum,
)
from app.models.enums import (
    DeliveryStatus,
    DeliveryType,
    RevisionReason,
    SectionStatus,
    Vote,
)


class Edition(Base):
    """One IST calendar day. Revisions of it share the edition number."""

    __tablename__ = "editions"

    id: Mapped[UuidPk]
    edition_date: Mapped[EditionDate] = mapped_column(unique=True)
    edition_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    special_edition_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_weekend: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[CreatedAt]

    revisions: Mapped[list[EditionRevision]] = relationship(back_populates="edition")

    __table_args__ = (CheckConstraint("edition_number > 0", name="edition_number_positive"),)


class EditionRevision(Base):
    """Immutable once published. A change means a new revision, never an edit."""

    __tablename__ = "edition_revisions"

    id: Mapped[UuidPk]
    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("editions.id", ondelete="RESTRICT"), nullable=False
    )
    revision: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reason: Mapped[RevisionReason] = mapped_column(
        pg_enum(RevisionReason, "revision_reason"), nullable=False
    )
    published_at: Mapped[Instant]
    created_at: Mapped[CreatedAt]

    edition: Mapped[Edition] = relationship(back_populates="revisions")
    sections: Mapped[list[EditionSection]] = relationship(back_populates="revision")

    __table_args__ = (
        UniqueConstraint("edition_id", "revision"),
        CheckConstraint("revision >= 1", name="revision_positive"),
    )


class EditionSection(Base):
    """A genre section, pre-rendered once per revision and reused per user."""

    __tablename__ = "edition_sections"

    id: Mapped[UuidPk]
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edition_revisions.id", ondelete="CASCADE"), nullable=False
    )
    genre: Mapped[GenreKeyColumn]
    status: Mapped[SectionStatus] = mapped_column(
        pg_enum(SectionStatus, "section_status"), nullable=False
    )
    html: Mapped[str | None] = mapped_column(Text, nullable=True)
    plain_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Object path of the pre-rendered PDF pages in Cloud Storage.
    pdf_object: Mapped[str | None] = mapped_column(Text, nullable=True)
    story_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[CreatedAt]

    revision: Mapped[EditionRevision] = relationship(back_populates="sections")

    __table_args__ = (
        UniqueConstraint("revision_id", "genre"),
        genre_check("genre", "genre"),
        CheckConstraint(
            "status <> 'ok' OR (html IS NOT NULL AND plain_text IS NOT NULL)",
            name="ok_sections_are_rendered",
        ),
    )


class Delivery(Base):
    """At-most-once send record, claimed with a row lock before the SMTP call.

    A row stuck in `sending` is never auto-resent; it is flagged for review,
    because the recipient may already have the email.
    """

    __tablename__ = "deliveries"

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    edition_date: Mapped[EditionDate]
    type: Mapped[DeliveryType] = mapped_column(
        pg_enum(DeliveryType, "delivery_type"), nullable=False
    )
    # The exact revision this recipient received; drives PDFs and corrections.
    revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edition_revisions.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[DeliveryStatus] = mapped_column(
        pg_enum(DeliveryStatus, "delivery_status"),
        nullable=False,
        default=DeliveryStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[OptionalInstant]
    sent_at: Mapped[OptionalInstant]
    created_at: Mapped[CreatedAt]

    revision: Mapped[EditionRevision | None] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "edition_date", "type"),
        Index("ix_deliveries_edition_date_status", "edition_date", "status"),
        CheckConstraint(
            "type <> 'newsletter' OR status <> 'sent' OR revision_id IS NOT NULL",
            name="sent_newsletters_record_their_revision",
        ),
    )


class Feedback(Base):
    """Thumbs up/down on a story. user_id is nulled when a user is deleted."""

    __tablename__ = "feedback"

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    vote: Mapped[Vote] = mapped_column(pg_enum(Vote, "vote"), nullable=False)
    # Cleared by the 04:00 aggregation job once folded into user_preferences.
    aggregated_at: Mapped[OptionalInstant]
    created_at: Mapped[CreatedAt]

    __table_args__ = (
        UniqueConstraint("user_id", "story_id"),
        Index("ix_feedback_aggregated_at", "aggregated_at"),
    )


__all__ = [
    "Delivery",
    "Edition",
    "EditionRevision",
    "EditionSection",
    "Feedback",
]

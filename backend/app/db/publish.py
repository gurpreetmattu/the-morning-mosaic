"""Publish an edition revision.

A revision is immutable once written. Correcting, withdrawing, or re-running
never edits one: it publishes the next revision, and readers already served
keep the revision they received (that is why `deliveries.revision_id` exists).

The edition itself is created once per IST calendar date and keeps its edition
number across every revision of that day.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.schemas import EditionBuild
from app.clock import now_utc
from app.models.editions import Edition, EditionRevision, EditionSection
from app.models.enums import RevisionReason, SectionStatus
from app.render.sections import RenderedSection


class PublishError(RuntimeError):
    """The revision could not be published."""


def publish_revision(
    session: Session,
    *,
    build: EditionBuild,
    sections: Mapping[str, RenderedSection],
    reason: RevisionReason = RevisionReason.BUILD,
    published_at: datetime | None = None,
) -> EditionRevision:
    if not any(section.status is SectionStatus.OK for section in sections.values()):
        # A revision with nothing publishable in it would still be served to
        # readers. Refuse, and let the failure policy send a notice instead.
        raise PublishError("refusing to publish a revision with no usable section")

    edition = _edition_for(session, build)
    revision = EditionRevision(
        edition_id=edition.id,
        revision=_next_revision(session, edition),
        reason=reason,
        published_at=published_at or now_utc(),
    )
    session.add(revision)
    session.flush()

    for rendered in sections.values():
        session.add(
            EditionSection(
                revision_id=revision.id,
                genre=rendered.genre,
                status=rendered.status,
                html=rendered.html,
                plain_text=rendered.plain_text,
                story_count=rendered.story_count,
            )
        )
    session.flush()
    return revision


def latest_revision(session: Session, edition_date: object) -> EditionRevision | None:
    """The newest published revision for a date, or None."""
    return session.scalar(
        select(EditionRevision)
        .join(Edition, Edition.id == EditionRevision.edition_id)
        .where(Edition.edition_date == edition_date)
        .order_by(EditionRevision.revision.desc())
        .limit(1)
    )


def _edition_for(session: Session, build: EditionBuild) -> Edition:
    existing = session.scalar(select(Edition).where(Edition.edition_date == build.edition_date))
    if existing is not None:
        if existing.edition_number != build.edition_number:
            raise PublishError(
                f"{build.edition_date} is already edition {existing.edition_number}; "
                f"this build computed {build.edition_number}. Revisions share a number, "
                "so one of them is wrong — check launch_date."
            )
        return existing

    edition = Edition(
        edition_date=build.edition_date,
        edition_number=build.edition_number,
        special_edition_key=build.special_edition_key,
        is_weekend=build.is_weekend,
    )
    session.add(edition)
    session.flush()
    return edition


def _next_revision(session: Session, edition: Edition) -> int:
    highest = session.scalar(
        select(func.max(EditionRevision.revision)).where(EditionRevision.edition_id == edition.id)
    )
    return (highest or 0) + 1

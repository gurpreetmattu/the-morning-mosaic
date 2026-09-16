"""The public archive.

Shows the non-personalised genre sections of each edition, which is exactly
what `edition_sections` already holds — the same bytes readers received,
without anyone's name or ordering on them.

An edition becomes public only after the last delivery slot at 09:00 IST. A
reader who chose the 09:00 slot must not be able to read today's edition on
the website before it reaches their inbox.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.clock import now_utc, to_ist
from app.db.publish import latest_revision
from app.models.editions import Edition, EditionSection
from app.models.enums import SectionStatus

router = APIRouter()

# The last delivery run. Before this, today's edition is still being sent.
PUBLIC_FROM_IST_HOUR = 9

MAX_LISTED = 60


class ArchivedSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    genre: str
    status: SectionStatus
    html: str
    story_count: int


class ArchivedEdition(BaseModel):
    model_config = ConfigDict(frozen=True)

    edition_date: date
    edition_number: int
    special_edition_key: str | None
    is_weekend: bool
    revision: int
    sections: list[ArchivedSection]


class EditionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    edition_date: date
    edition_number: int
    special_edition_key: str | None


def is_public(edition_date: date, *, now: datetime | None = None) -> bool:
    """True once the edition has finished being delivered."""
    moment = to_ist(now or now_utc())
    if edition_date < moment.date():
        return True
    if edition_date > moment.date():
        return False
    return moment.hour >= PUBLIC_FROM_IST_HOUR


@router.get("/api/archive", response_model=list[EditionSummary])
def list_editions(session: Annotated[Session, Depends(db_session)]) -> list[EditionSummary]:
    editions = session.scalars(
        select(Edition).order_by(Edition.edition_date.desc()).limit(MAX_LISTED)
    )
    return [
        EditionSummary(
            edition_date=edition.edition_date,
            edition_number=edition.edition_number,
            special_edition_key=edition.special_edition_key,
        )
        for edition in editions
        if is_public(edition.edition_date)
    ]


@router.get("/api/archive/{edition_date}", response_model=ArchivedEdition)
def read_edition(
    edition_date: date, session: Annotated[Session, Depends(db_session)]
) -> ArchivedEdition:
    if not is_public(edition_date):
        # Indistinguishable from an edition that never existed: a reader
        # cannot use the archive to learn what is coming.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such edition.")

    edition = session.scalar(select(Edition).where(Edition.edition_date == edition_date))
    revision = latest_revision(session, edition_date)
    if edition is None or revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such edition.")

    sections = session.scalars(
        select(EditionSection)
        .where(EditionSection.revision_id == revision.id)
        .order_by(EditionSection.genre)
    )
    return ArchivedEdition(
        edition_date=edition.edition_date,
        edition_number=edition.edition_number,
        special_edition_key=edition.special_edition_key,
        is_weekend=edition.is_weekend,
        revision=revision.revision,
        sections=[
            ArchivedSection(
                genre=row.genre,
                status=row.status,
                html=row.html or "",
                story_count=row.story_count,
            )
            for row in sections
        ],
    )

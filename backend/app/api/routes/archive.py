"""The public archive.

Shows the non-personalised genre sections of each edition, which is exactly
what `edition_sections` already holds — the same bytes readers received,
without anyone's name or ordering on them.

An edition becomes public only after the last delivery slot at 09:00 IST. A
reader who chose the 09:00 slot must not be able to read today's edition on
the website before it reaches their inbox.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.clock import now_utc, to_ist
from app.db.publish import latest_revision
from app.models.content import Correction, Story
from app.models.editions import Edition, EditionSection
from app.models.enums import SectionStatus, StoryStatus

router = APIRouter()

# The last delivery run. Before this, today's edition is still being sent.
PUBLIC_FROM_IST_HOUR = 9

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 60


class ArchivedSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    genre: str
    status: SectionStatus
    html: str
    story_count: int


class CorrectionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    story_headline: str
    genre: str
    description: str
    corrected_at: datetime


class ArchivedEdition(BaseModel):
    model_config = ConfigDict(frozen=True)

    edition_date: date
    edition_number: int
    special_edition_key: str | None
    is_weekend: bool
    revision: int
    sections: list[ArchivedSection]
    # Layered on top of the frozen section HTML above, never inside it:
    # published content is never edited, so a correction is always shown
    # alongside the original, not as a change to it.
    corrections: list[CorrectionSummary]


class EditionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    edition_date: date
    edition_number: int
    special_edition_key: str | None


class ArchivePage(BaseModel):
    model_config = ConfigDict(frozen=True)

    editions: list[EditionSummary]
    has_more: bool


class LatestHighlight(BaseModel):
    model_config = ConfigDict(frozen=True)

    genre: str
    headline: str
    one_liner: str


class LatestHighlights(BaseModel):
    model_config = ConfigDict(frozen=True)

    edition_date: date
    edition_number: int
    items: list[LatestHighlight]


# The landing page shows a handful of real headlines, not a whole edition.
MAX_HIGHLIGHTS = 3


def is_public(edition_date: date, *, now: datetime | None = None) -> bool:
    """True once the edition has finished being delivered."""
    moment = to_ist(now or now_utc())
    if edition_date < moment.date():
        return True
    if edition_date > moment.date():
        return False
    return moment.hour >= PUBLIC_FROM_IST_HOUR


def _latest_public_date(now: datetime | None = None) -> date:
    """The newest `edition_date` a listing may show, given the time.

    Pushing this into the query (rather than fetching and filtering in
    Python, as this route used to) keeps `limit`/`has_more` exact: at most
    one edition — today's — is ever not yet public, so filtering it out
    afterwards could silently short a page by one.
    """
    moment = to_ist(now or now_utc())
    if moment.hour >= PUBLIC_FROM_IST_HOUR:
        return moment.date()
    return moment.date() - timedelta(days=1)


@router.get("/api/archive", response_model=ArchivePage)
def list_editions(
    session: Annotated[Session, Depends(db_session)],
    before: date | None = None,
    limit: Annotated[int, Query(gt=0)] = DEFAULT_LIST_LIMIT,
) -> ArchivePage:
    capped = min(limit, MAX_LIST_LIMIT)
    query = (
        select(Edition)
        .where(Edition.edition_date <= _latest_public_date())
        .order_by(Edition.edition_date.desc())
    )
    if before is not None:
        query = query.where(Edition.edition_date < before)

    # One extra row, never returned, just to know whether another page exists.
    rows = list(session.scalars(query.limit(capped + 1)))
    return ArchivePage(
        editions=[
            EditionSummary(
                edition_date=edition.edition_date,
                edition_number=edition.edition_number,
                special_edition_key=edition.special_edition_key,
            )
            for edition in rows[:capped]
        ],
        has_more=len(rows) > capped,
    )


@router.get("/api/latest-edition", response_model=LatestHighlights)
def latest_highlights(session: Annotated[Session, Depends(db_session)]) -> LatestHighlights:
    """The newest public edition's top verified story per genre, for the landing page.

    Only stories that are still verified, have a verified one-liner, and carry
    no correction are offered, and only from genres whose section published
    normally. When in doubt a story is left out: a short list is fine, a wrong
    one is not. 404 until the first edition is public.
    """
    edition = session.scalar(
        select(Edition)
        .where(Edition.edition_date <= _latest_public_date())
        .order_by(Edition.edition_date.desc())
        .limit(1)
    )
    revision = latest_revision(session, edition.edition_date) if edition else None
    if edition is None or revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No edition yet.")

    ok_genres = set(
        session.scalars(
            select(EditionSection.genre).where(
                EditionSection.revision_id == revision.id,
                EditionSection.status == SectionStatus.OK,
            )
        )
    )
    corrected = select(Correction.story_id)
    stories = session.scalars(
        select(Story)
        .where(
            Story.edition_date == edition.edition_date,
            Story.status == StoryStatus.VERIFIED,
            Story.one_liner.is_not(None),
            Story.genre.in_(ok_genres),
            Story.id.not_in(corrected),
        )
        .order_by(Story.pool_rank, Story.genre)
    )

    items: list[LatestHighlight] = []
    seen: set[str] = set()
    for story in stories:
        if story.genre in seen or not story.one_liner:
            continue
        seen.add(story.genre)
        items.append(
            LatestHighlight(genre=story.genre, headline=story.headline, one_liner=story.one_liner)
        )
        if len(items) == MAX_HIGHLIGHTS:
            break
    return LatestHighlights(
        edition_date=edition.edition_date, edition_number=edition.edition_number, items=items
    )


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
    corrections = session.execute(
        select(Correction, Story)
        .join(Story, Story.id == Correction.story_id)
        .where(Story.edition_date == edition_date)
        .order_by(Correction.corrected_at)
    ).all()
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
        corrections=[
            CorrectionSummary(
                story_headline=story.headline,
                genre=story.genre,
                description=correction.description,
                corrected_at=correction.corrected_at,
            )
            for correction, story in corrections
        ],
    )

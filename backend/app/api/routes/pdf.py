"""The PDF download link every email and archive page carries.

Reader-facing, but not link-scanner-safe in the opt-in/unsubscribe sense:
downloading a document changes nothing about the reader's account, so a
scanner opening it early is harmless — at worst it warms the cache. The GET
is the whole route.

The token is stateless and never expires (`app/email/tokens.py`, purpose
`PDF`), bound to one revision and one reader: `sign(PDF, revision_id,
user=user_id)` in `app/jobs/delivery.py`. That is what makes "the PDF a
reader downloads is the edition they were sent, not a later one" true —
the assembly below reads `EditionSection` rows scoped to that exact
`revision_id`, never the live story table, so a late update on the same day
cannot change what an already-issued link produces.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import pages
from app.api.deps import db_session
from app.api.deps import settings as get_request_settings
from app.config.loader import load_genres
from app.config.settings import Settings
from app.email import tokens
from app.email.tokens import TokenError
from app.models.editions import Edition, EditionRevision, EditionSection
from app.models.enums import SectionStatus
from app.models.users import User, UserGenre
from app.render.pdf import PdfAssembler, PdfSection
from app.render.pdf import weasyprint_renderer as render_pdf_html
from app.storage import ObjectStorage, get_object_storage

logger = logging.getLogger(__name__)

router = APIRouter()


def _reader_cache_key(revision_id: uuid.UUID, user_id: uuid.UUID) -> str:
    return f"pdf/readers/{revision_id}/{user_id}.pdf"


def assemble_reader_pdf(
    session: Session,
    storage: ObjectStorage,
    assembler: PdfAssembler,
    *,
    revision: EditionRevision,
    user: User,
) -> bytes | None:
    """None means this reader has nothing to show for this revision."""
    subscribed = set(session.scalars(select(UserGenre.genre).where(UserGenre.user_id == user.id)))
    if not subscribed:
        return None

    genre_settings = {g.key: g for g in load_genres().genres if g.key in subscribed}
    rows = {
        row.genre: row
        for row in session.scalars(
            select(EditionSection).where(
                EditionSection.revision_id == revision.id,
                EditionSection.status == SectionStatus.OK,
            )
        )
    }

    sections: list[PdfSection] = []
    for genre, settings in genre_settings.items():
        row = rows.get(genre)
        if row is None:
            continue
        assert row.html is not None  # enforced by the ok_sections_are_rendered CHECK
        sections.append(
            PdfSection(
                genre=genre, title=settings.section_title, blurb=settings.blurb, html=row.html
            )
        )
    if not sections:
        return None

    edition = session.get(Edition, revision.edition_id)
    assert edition is not None
    return assembler.render_edition(
        first_name=user.name.split()[0] if user.name.strip() else "there",
        edition_date=edition.edition_date,
        edition_number=edition.edition_number,
        sections=sections,
    )


@router.get("/pdf/{token}")
def download_pdf(
    token: str,
    session: Annotated[Session, Depends(db_session)],
    config: Annotated[Settings, Depends(get_request_settings)],
) -> Response:
    try:
        claims = tokens.verify(token, tokens.PDF)
        revision_id = uuid.UUID(claims.subject)
        user_id = uuid.UUID(str(claims.extra["user"]))
    except (TokenError, KeyError, ValueError):
        return pages.gone(title="That link is not valid", body="We couldn't read that link.")

    revision = session.get(EditionRevision, revision_id)
    user = session.get(User, user_id)
    if revision is None or user is None or user.anonymised_at is not None:
        return pages.gone(
            title="That link is not valid", body="We couldn't find the edition it refers to."
        )

    storage = get_object_storage(config)
    reader_key = _reader_cache_key(revision_id, user_id)
    pdf_bytes = storage.get(reader_key)

    if pdf_bytes is None:
        assembler = PdfAssembler(render_html=render_pdf_html)
        pdf_bytes = assemble_reader_pdf(session, storage, assembler, revision=revision, user=user)
        if pdf_bytes is None:
            return pages.gone(
                title="Nothing to show",
                body="This edition had no sections for your subscribed genres.",
            )
        storage.put(reader_key, pdf_bytes, content_type="application/pdf")

    edition = session.get(Edition, revision.edition_id)
    assert edition is not None
    filename = f"the-morning-mosaic-{edition.edition_date.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )

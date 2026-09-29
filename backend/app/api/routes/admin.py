"""The admin dashboard's API: one allowlisted owner, a handful of levers.

CLAUDE.md: "Admin dashboard: magic-link login restricted to an allowlisted
owner email." There is no admin table — only `ADMIN_EMAIL` — and no
frontend yet either, so this is the backend half: authentication, the reads
that make the gaps recorded in docs/BACKLOG.md visible (stuck deliveries,
recent job runs, held notice batches), and the two writes CLAUDE.md actually
specifies for a human: approving or suppressing a held failure-notice batch,
and withdrawing a story.

Every write below re-uses the job logic it stands in for rather than
re-implementing it:

- Approving or suppressing a batch only flips `NoticeBatch.status`. The
  failure-notice job already re-reads that row every time it runs ("jobs are
  safe to rerun"), so the actual sending happens on its own next run, not
  here.
- Withdrawing a story publishes a new revision the same way the late update
  job does: mark the story, re-render only the genre it was in from what
  remains, and carry every other section forward byte for byte.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.schemas import EditionBuild
from app.api import pages
from app.api.admin_session import (
    clear_admin_session,
    issue_admin_session,
    require_admin,
    require_admin_csrf,
)
from app.api.deps import db_session
from app.api.deps import settings as get_request_settings
from app.api.security import RateLimiter, client_key
from app.clock import now_utc
from app.config.schemas import GenreKey
from app.config.settings import Settings
from app.db.publish import PublishError, latest_revision, publish_revision
from app.email import tokens
from app.email.sender import Message, Sender
from app.email.tokens import TokenError
from app.models.content import Correction, Story, StoryWithdrawal
from app.models.editions import Delivery, Edition, EditionSection
from app.models.enums import (
    DeliveryStatus,
    JobName,
    NoticeBatchStatus,
    RevisionReason,
    RunStatus,
    StoryStatus,
)
from app.models.operations import NoticeBatch, PipelineRun, SiteStatus
from app.render.email import BRAND
from app.render.sections import RenderedSection, SectionRenderer
from app.render.selection import load_candidates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin")

admin_login_limiter = RateLimiter(name="admin_login", limit=5, window_seconds=300)

DEFAULT_LIST_LIMIT = 30
MAX_LIST_LIMIT = 100
# A row this old in `sending` was not just claimed a moment ago by a run
# that's still mid-flight; it's the kind CLAUDE.md wants "flagged for review".
STUCK_AFTER_MINUTES = 30


def _is_admin_email(email: str, settings: Settings) -> bool:
    return email.strip().lower() == settings.admin_email.strip().lower()


# ------------------------------------------------------------------ login


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


@router.post("/api/login")
def request_admin_login(
    payload: AdminLoginRequest,
    request: Request,
    session: Annotated[Session, Depends(db_session)],
    config: Annotated[Settings, Depends(get_request_settings)],
) -> JSONResponse:
    admin_login_limiter.enforce(session, client_key(request))

    if _is_admin_email(payload.email, config):
        _send_admin_login_link(config)

    return JSONResponse(
        {
            "status": "check_your_email",
            "message": "If that's the admin address, a link is on its way.",
        }
    )


@router.get("/login/{token}", response_class=HTMLResponse)
def admin_login_page(token: str) -> HTMLResponse:
    return pages.confirm(
        title="Admin sign-in",
        body=f"Press the button to sign in to the {BRAND} admin dashboard.",
        action=f"/admin/login/{token}",
        label="Sign in",
    )


@router.post("/login/{token}", response_class=HTMLResponse)
def admin_login_confirm(
    token: str, config: Annotated[Settings, Depends(get_request_settings)]
) -> HTMLResponse:
    try:
        claims = tokens.verify(token, tokens.ADMIN_LOGIN)
    except TokenError:
        return pages.gone(
            title="That link has expired",
            body="Admin sign-in links last 15 minutes. Request a fresh one.",
        )

    if not _is_admin_email(claims.subject, config):
        return pages.gone(title="That link is no longer valid", body="")

    html = pages.done(title="You're signed in", body="You can return to the admin dashboard now.")
    issue_admin_session(html, admin_email=claims.subject, settings=config)
    return html


@router.post("/api/logout")
def admin_logout(_csrf: Annotated[None, Depends(require_admin_csrf)]) -> JSONResponse:
    response = JSONResponse({"status": "signed_out"})
    clear_admin_session(response)
    return response


@router.get("/api/me")
def admin_me(admin_email: Annotated[str, Depends(require_admin)]) -> dict[str, str]:
    return {"email": admin_email}


# ----------------------------------------------------------------- reads


class RunSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    job: JobName
    edition_date: date | None
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    deadline_at: datetime | None
    detail: dict[str, Any] | None


@router.get("/api/runs", response_model=list[RunSummary])
def list_runs(
    admin_email: Annotated[str, Depends(require_admin)],
    session: Annotated[Session, Depends(db_session)],
    job: JobName | None = None,
    edition_date: date | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
) -> list[RunSummary]:
    query = select(PipelineRun).order_by(PipelineRun.started_at.desc())
    if job is not None:
        query = query.where(PipelineRun.job == job)
    if edition_date is not None:
        query = query.where(PipelineRun.edition_date == edition_date)
    rows = session.scalars(query.limit(min(limit, MAX_LIST_LIMIT)))
    return [
        RunSummary(
            id=row.id,
            job=row.job,
            edition_date=row.edition_date,
            status=row.status,
            started_at=row.started_at,
            finished_at=row.finished_at,
            deadline_at=row.deadline_at,
            detail=row.detail,
        )
        for row in rows
    ]


class StuckDelivery(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    edition_date: date
    type: str
    attempts: int
    claimed_at: datetime | None


@router.get("/api/deliveries/stuck", response_model=list[StuckDelivery])
def list_stuck_deliveries(
    admin_email: Annotated[str, Depends(require_admin)],
    session: Annotated[Session, Depends(db_session)],
) -> list[StuckDelivery]:
    """Rows CLAUDE.md says to flag for review: never auto-resent, so they
    only clear once a human looks at them.

    Excludes a row claimed moments ago — that is a run still mid-flight, not
    yet the kind stuck between the SMTP call and its result.
    """
    threshold = now_utc() - timedelta(minutes=STUCK_AFTER_MINUTES)
    rows = session.scalars(
        select(Delivery)
        .where(Delivery.status == DeliveryStatus.SENDING, Delivery.claimed_at <= threshold)
        .order_by(Delivery.claimed_at)
    )
    return [
        StuckDelivery(
            id=row.id,
            user_id=row.user_id,
            edition_date=row.edition_date,
            type=row.type.value,
            attempts=row.attempts,
            claimed_at=row.claimed_at,
        )
        for row in rows
    ]


class NoticeBatchSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    edition_date: date
    status: NoticeBatchStatus
    recipient_count: int
    expires_at: datetime
    decided_at: datetime | None
    decided_by: str | None


@router.get("/api/notices", response_model=list[NoticeBatchSummary])
def list_notice_batches(
    admin_email: Annotated[str, Depends(require_admin)],
    session: Annotated[Session, Depends(db_session)],
    limit: int = DEFAULT_LIST_LIMIT,
) -> list[NoticeBatchSummary]:
    rows = session.scalars(
        select(NoticeBatch)
        .order_by(NoticeBatch.edition_date.desc())
        .limit(min(limit, MAX_LIST_LIMIT))
    )
    return [
        NoticeBatchSummary(
            edition_date=row.edition_date,
            status=row.status,
            recipient_count=row.recipient_count,
            expires_at=row.expires_at,
            decided_at=row.decided_at,
            decided_by=row.decided_by,
        )
        for row in rows
    ]


def _decide_batch(
    session: Session,
    *,
    edition_date: date,
    admin_email: str,
    allowed_from: tuple[NoticeBatchStatus, ...],
    new_status: NoticeBatchStatus,
) -> NoticeBatchSummary:
    batch = session.scalar(select(NoticeBatch).where(NoticeBatch.edition_date == edition_date))
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No notice batch for that date.")
    if batch.status not in allowed_from:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A batch that is {batch.status.value} cannot be moved to {new_status.value}.",
        )

    batch.status = new_status
    batch.decided_at = now_utc()
    batch.decided_by = admin_email
    session.flush()
    return NoticeBatchSummary(
        edition_date=batch.edition_date,
        status=batch.status,
        recipient_count=batch.recipient_count,
        expires_at=batch.expires_at,
        decided_at=batch.decided_at,
        decided_by=batch.decided_by,
    )


@router.post("/api/notices/{edition_date}/approve", response_model=NoticeBatchSummary)
def approve_notice_batch(
    edition_date: date,
    admin_email: Annotated[str, Depends(require_admin)],
    session: Annotated[Session, Depends(db_session)],
    _csrf: Annotated[None, Depends(require_admin_csrf)],
) -> NoticeBatchSummary:
    return _decide_batch(
        session,
        edition_date=edition_date,
        admin_email=admin_email,
        allowed_from=(NoticeBatchStatus.HELD,),
        new_status=NoticeBatchStatus.APPROVED,
    )


@router.post("/api/notices/{edition_date}/suppress", response_model=NoticeBatchSummary)
def suppress_notice_batch(
    edition_date: date,
    admin_email: Annotated[str, Depends(require_admin)],
    session: Annotated[Session, Depends(db_session)],
    _csrf: Annotated[None, Depends(require_admin_csrf)],
) -> NoticeBatchSummary:
    return _decide_batch(
        session,
        edition_date=edition_date,
        admin_email=admin_email,
        allowed_from=(NoticeBatchStatus.HELD, NoticeBatchStatus.APPROVED),
        new_status=NoticeBatchStatus.SUPPRESSED,
    )


# ------------------------------------------------------------- kill switch


class WithdrawRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class WithdrawResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    story_id: uuid.UUID
    genre: str
    revision: int
    remaining_stories: int


class WithdrawalSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    story_id: uuid.UUID
    headline: str
    genre: str
    edition_date: date
    reason: str
    withdrawn_at: datetime


def _carry_forward(
    session: Session, *, revision_id: uuid.UUID, except_genre: str
) -> dict[str, RenderedSection]:
    """The rest of the previous revision, unchanged, byte for byte."""
    sections: dict[str, RenderedSection] = {}
    for row in session.scalars(
        select(EditionSection).where(EditionSection.revision_id == revision_id)
    ):
        if row.genre == except_genre:
            continue
        sections[row.genre] = RenderedSection(
            genre=row.genre,
            status=row.status,
            html=row.html or "",
            plain_text=row.plain_text or "",
            story_count=row.story_count,
        )
    return sections


@router.post("/api/stories/{story_id}/withdraw", response_model=WithdrawResponse)
def withdraw_story(
    story_id: uuid.UUID,
    payload: WithdrawRequest,
    admin_email: Annotated[str, Depends(require_admin)],
    session: Annotated[Session, Depends(db_session)],
    _csrf: Annotated[None, Depends(require_admin_csrf)],
) -> WithdrawResponse:
    story = session.get(Story, story_id)
    if story is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such story.")
    if story.status is StoryStatus.WITHDRAWN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That story is already withdrawn.")

    revision = latest_revision(session, story.edition_date)
    if revision is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No published revision to update.")

    edition = session.get(Edition, revision.edition_id)
    assert edition is not None

    story.status = StoryStatus.WITHDRAWN
    session.add(StoryWithdrawal(story_id=story.id, reason=payload.reason, withdrawn_at=now_utc()))
    session.flush()

    genre = story.genre
    sections = _carry_forward(session, revision_id=revision.id, except_genre=genre)
    remaining = sorted(
        load_candidates(session, edition_date=story.edition_date, genres=[genre]),  # type: ignore[list-item]
        key=lambda candidate: candidate.pool_rank,
    )
    sections[genre] = SectionRenderer().render_candidates(genre, remaining)  # type: ignore[arg-type]

    try:
        new_revision = publish_revision(
            session,
            build=EditionBuild(
                edition_date=story.edition_date,
                edition_number=edition.edition_number,
                special_edition_key=edition.special_edition_key,
                is_weekend=edition.is_weekend,
                genres=[],
            ),
            sections=sections,
            reason=RevisionReason.WITHDRAWAL,
            published_at=now_utc(),
        )
    except PublishError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    logger.info(
        "story withdrawn",
        extra={"story_id": str(story.id), "admin_email": admin_email, "genre": genre},
    )
    return WithdrawResponse(
        story_id=story.id,
        genre=genre,
        revision=new_revision.revision,
        remaining_stories=len(remaining),
    )


class SectionWithdrawResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    genre: str
    revision: int
    stories_withdrawn: int


@router.post(
    "/api/editions/{edition_date}/sections/{genre}/withdraw",
    response_model=SectionWithdrawResponse,
)
def withdraw_section(
    edition_date: date,
    genre: GenreKey,
    payload: WithdrawRequest,
    admin_email: Annotated[str, Depends(require_admin)],
    session: Annotated[Session, Depends(db_session)],
    _csrf: Annotated[None, Depends(require_admin_csrf)],
) -> SectionWithdrawResponse:
    """Withdraw every active story in one section at once: the same
    published result as withdrawing each of its stories by hand, in one
    call and one revision instead of one per story."""
    revision = latest_revision(session, edition_date)
    if revision is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No published revision to update.")

    edition = session.get(Edition, revision.edition_id)
    assert edition is not None

    active = session.scalars(
        select(Story).where(
            Story.edition_date == edition_date,
            Story.genre == genre,
            Story.status != StoryStatus.WITHDRAWN,
        )
    ).all()
    if not active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That section has no active stories.")

    withdrawn_at = now_utc()
    for story in active:
        story.status = StoryStatus.WITHDRAWN
        session.add(
            StoryWithdrawal(story_id=story.id, reason=payload.reason, withdrawn_at=withdrawn_at)
        )
    session.flush()

    sections = _carry_forward(session, revision_id=revision.id, except_genre=genre)
    sections[genre] = SectionRenderer().render_candidates(genre, [])

    try:
        new_revision = publish_revision(
            session,
            build=EditionBuild(
                edition_date=edition_date,
                edition_number=edition.edition_number,
                special_edition_key=edition.special_edition_key,
                is_weekend=edition.is_weekend,
                genres=[],
            ),
            sections=sections,
            reason=RevisionReason.WITHDRAWAL,
            published_at=now_utc(),
        )
    except PublishError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    logger.info(
        "section withdrawn",
        extra={
            "edition_date": str(edition_date),
            "genre": genre,
            "admin_email": admin_email,
            "stories_withdrawn": len(active),
        },
    )
    return SectionWithdrawResponse(
        genre=genre, revision=new_revision.revision, stories_withdrawn=len(active)
    )


@router.get("/api/withdrawals", response_model=list[WithdrawalSummary])
def list_withdrawals(
    admin_email: Annotated[str, Depends(require_admin)],
    session: Annotated[Session, Depends(db_session)],
    limit: int = DEFAULT_LIST_LIMIT,
) -> list[WithdrawalSummary]:
    rows = session.execute(
        select(StoryWithdrawal, Story)
        .join(Story, Story.id == StoryWithdrawal.story_id)
        .order_by(StoryWithdrawal.withdrawn_at.desc())
        .limit(min(limit, MAX_LIST_LIMIT))
    ).all()
    return [
        WithdrawalSummary(
            story_id=story.id,
            headline=story.headline,
            genre=story.genre,
            edition_date=story.edition_date,
            reason=withdrawal.reason,
            withdrawn_at=withdrawal.withdrawn_at,
        )
        for withdrawal, story in rows
    ]


# ---------------------------------------------------------------- corrections


class CorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=1000)


class CorrectionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    story_id: uuid.UUID
    description: str
    corrected_at: datetime


class CorrectionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    story_id: uuid.UUID
    headline: str
    genre: str
    edition_date: date
    description: str
    corrected_at: datetime
    announced_on: date | None


@router.post("/api/stories/{story_id}/correct", response_model=CorrectionResponse)
def correct_story(
    story_id: uuid.UUID,
    payload: CorrectionRequest,
    admin_email: Annotated[str, Depends(require_admin)],
    session: Annotated[Session, Depends(db_session)],
    _csrf: Annotated[None, Depends(require_admin_csrf)],
) -> CorrectionResponse:
    """Records that a published story was wrong. Never edits the story
    itself — the archive shows this alongside the frozen section HTML
    (`GET /api/archive/{edition_date}`), and the delivery job includes a
    note in the next edition for readers who received the original
    (`app/jobs/delivery.py`'s `pending_corrections`). Withdrawing the story
    too, if it hasn't finished sending today, is a separate action
    (`POST /api/stories/{id}/withdraw`) — a correction alone doesn't stop
    a still-in-flight send.
    """
    story = session.get(Story, story_id)
    if story is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such story.")

    corrected_at = now_utc()
    session.add(
        Correction(story_id=story.id, description=payload.description, corrected_at=corrected_at)
    )
    session.flush()

    logger.info(
        "story corrected",
        extra={"story_id": str(story.id), "admin_email": admin_email},
    )
    return CorrectionResponse(
        story_id=story.id, description=payload.description, corrected_at=corrected_at
    )


@router.get("/api/corrections", response_model=list[CorrectionSummary])
def list_corrections(
    admin_email: Annotated[str, Depends(require_admin)],
    session: Annotated[Session, Depends(db_session)],
    limit: int = DEFAULT_LIST_LIMIT,
) -> list[CorrectionSummary]:
    rows = session.execute(
        select(Correction, Story)
        .join(Story, Story.id == Correction.story_id)
        .order_by(Correction.corrected_at.desc())
        .limit(min(limit, MAX_LIST_LIMIT))
    ).all()
    return [
        CorrectionSummary(
            story_id=story.id,
            headline=story.headline,
            genre=story.genre,
            edition_date=story.edition_date,
            description=correction.description,
            corrected_at=correction.corrected_at,
            announced_on=correction.announced_on,
        )
        for correction, story in rows
    ]


# -------------------------------------------------------------------- status


class StatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    degraded: bool
    message: str | None = Field(default=None, max_length=500)


class AdminStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    degraded: bool
    message: str | None
    updated_at: datetime


@router.get("/api/status", response_model=AdminStatusResponse)
def read_status_admin(
    admin_email: Annotated[str, Depends(require_admin)],
    session: Annotated[Session, Depends(db_session)],
) -> AdminStatusResponse:
    """The dashboard's own view of the same row `GET /api/status` serves
    publicly — a real `updated_at` even when nothing has ever been set, so
    the form has a sensible starting point rather than guessing."""
    row = session.get(SiteStatus, 1)
    if row is None:
        return AdminStatusResponse(degraded=False, message=None, updated_at=now_utc())
    return AdminStatusResponse(
        degraded=row.degraded, message=row.message, updated_at=row.updated_at
    )


@router.post("/api/status", response_model=AdminStatusResponse)
def set_status(
    payload: StatusRequest,
    admin_email: Annotated[str, Depends(require_admin)],
    session: Annotated[Session, Depends(db_session)],
    _csrf: Annotated[None, Depends(require_admin_csrf)],
) -> AdminStatusResponse:
    """CLAUDE.md: "Website downtime is shown as a status message on the
    site, not emailed, unless it stops the newsletter." Manual on purpose —
    see `SiteStatus`'s own docstring for why there's no automated trigger
    yet. `GET /api/status` (no auth) is what the public status page reads."""
    moment = now_utc()
    row = session.get(SiteStatus, 1)
    if row is None:
        row = SiteStatus(
            id=1, degraded=payload.degraded, message=payload.message, updated_at=moment
        )
        session.add(row)
    else:
        row.degraded = payload.degraded
        row.message = payload.message
        row.updated_at = moment
    session.flush()

    logger.info(
        "site status changed",
        extra={"degraded": payload.degraded, "admin_email": admin_email},
    )
    return AdminStatusResponse(
        degraded=row.degraded, message=row.message, updated_at=row.updated_at
    )


# ---------------------------------------------------------------- helpers


def _send_admin_login_link(config: Settings) -> None:
    raw = tokens.sign(tokens.ADMIN_LOGIN, config.admin_email, expires_in=tokens.ADMIN_LOGIN_TTL)
    base = str(config.base_url).rstrip("/")
    link = f"{base}/admin/login/{raw}"

    Sender(settings=config).send(
        Message(
            to=config.admin_email,
            subject=f"Sign in to the {BRAND} admin dashboard",
            html=(
                f'<p>Sign in:</p><p><a href="{link}">Sign in</a></p>'
                "<p>This link expires in 15 minutes.</p>"
            ),
            text=f"Sign in:\n{link}\n\nThis link expires in 15 minutes.",
        )
    )

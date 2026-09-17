"""Passwordless account access: magic-link login, preferences, and DPDP rights.

The magic link follows the same shape as every other emailed link (see
`routes/public.py`): a GET renders a page and changes nothing, a POST does
the work. Everything past login is a plain JSON API behind a session cookie,
called by the site's own frontend, so those routes need the CSRF check
instead — a browser cookie is sent automatically by *any* site's forms; the
CSRF header can only be attached by script running on this origin.
"""

from __future__ import annotations

import logging
import uuid
from datetime import time as clock_time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api import pages
from app.api.deps import db_session
from app.api.deps import settings as get_request_settings
from app.api.routes.public import DELIVERY_SLOTS
from app.api.security import RateLimiter, client_key
from app.api.session import clear_session, issue_session, require_csrf, require_user
from app.clock import now_utc
from app.config.schemas import GENRE_KEYS, GenreKey
from app.config.settings import Settings
from app.email import tokens
from app.email.sender import Message, Sender
from app.email.tokens import TokenError
from app.models.editions import Delivery, Feedback
from app.models.enums import EditionPreference, Frequency, SubscriptionStatus, TokenPurpose
from app.models.users import City, Consent, FollowedKeyword, Token, User, UserGenre
from app.render.email import BRAND

logger = logging.getLogger(__name__)

router = APIRouter()

# A magic link, like signup, is an unauthenticated write (it sends mail), so
# it gets the same protection.
login_limiter = RateLimiter(name="account_login", limit=5, window_seconds=300)


# ------------------------------------------------------------------ request


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


@router.post("/api/login")
def request_login(
    payload: LoginRequest,
    request: Request,
    session: Annotated[Session, Depends(db_session)],
    config: Annotated[Settings, Depends(get_request_settings)],
) -> JSONResponse:
    login_limiter.enforce(session, client_key(request))

    address = payload.email.lower()
    user = session.scalar(select(User).where(User.email == address))
    # Never reveal whether an address has an account: the response is the
    # same either way.
    if user is not None and user.anonymised_at is None:
        _send_login_link(session, user, config)

    return JSONResponse(
        {
            "status": "check_your_email",
            "message": "If that address has an account, we've sent a sign-in link.",
        }
    )


@router.get("/login/{token}", response_class=HTMLResponse)
def login_page(token: str) -> HTMLResponse:
    return pages.confirm(
        title="Sign in",
        body=f"Press the button to sign in to {BRAND}.",
        action=f"/login/{token}",
        label="Sign in",
    )


@router.post("/login/{token}", response_class=HTMLResponse)
def login_confirm(
    token: str,
    session: Annotated[Session, Depends(db_session)],
    config: Annotated[Settings, Depends(get_request_settings)],
) -> HTMLResponse:
    try:
        stored = tokens.redeem(session, token, TokenPurpose.MAGIC_LINK)
    except TokenError:
        return pages.gone(
            title="That link has expired",
            body="Sign-in links last 30 minutes. Request a fresh one from the site.",
        )

    user = session.get(User, stored.user_id) if stored.user_id else None
    if user is None or user.anonymised_at is not None:
        return pages.gone(
            title="That link is no longer valid",
            body="We couldn't find the account it belongs to.",
        )

    html = pages.done(
        title="You're signed in",
        body="You can close this tab and return to the site to manage your preferences.",
    )
    issue_session(html, user_id=user.id, settings=config)
    return html


@router.post("/api/logout")
def logout(
    request: Request,
    _csrf: Annotated[None, Depends(require_csrf)],
) -> JSONResponse:
    response = JSONResponse({"status": "signed_out"})
    clear_session(response)
    return response


# --------------------------------------------------------------- preferences


class MeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    email: str
    name: str
    city_id: str | None
    status: SubscriptionStatus
    delivery_slot: clock_time
    frequency: Frequency
    edition_preference: EditionPreference
    language: str
    genres: list[str]
    keywords: list[str]


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    city_id: str | None = None
    genres: list[GenreKey] | None = Field(default=None, min_length=1, max_length=len(GENRE_KEYS))
    delivery_slot: clock_time | None = None
    frequency: Literal["daily", "weekdays"] | None = None
    edition_preference: Literal["india", "global", "mixed"] | None = None
    keywords: list[str] | None = Field(default=None, max_length=10)


def _profile(user: User) -> MeResponse:
    return MeResponse(
        email=user.email,
        name=user.name,
        city_id=user.city_id,
        status=user.status,
        delivery_slot=user.delivery_slot,
        frequency=user.frequency,
        edition_preference=user.edition_preference,
        language=user.language,
        genres=sorted(genre.genre for genre in user.genres),
        keywords=sorted(keyword.keyword for keyword in user.keywords),
    )


def _load_account(session: Session, user_id: uuid.UUID) -> User:
    """The signed-in user, refusing a session left over from a deleted account."""
    user = session.get(User, user_id)
    if user is None or user.anonymised_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required.")
    return user


@router.get("/api/me", response_model=MeResponse)
def read_me(
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    session: Annotated[Session, Depends(db_session)],
) -> MeResponse:
    return _profile(_load_account(session, user_id))


@router.patch("/api/me", response_model=MeResponse)
def update_me(
    payload: PreferencesUpdate,
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    session: Annotated[Session, Depends(db_session)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> JSONResponse | MeResponse:
    user = _load_account(session, user_id)
    fields = payload.model_fields_set

    if "name" in fields and payload.name is not None:
        user.name = payload.name.strip()

    if "city_id" in fields:
        if payload.city_id is not None and session.get(City, payload.city_id) is None:
            return _error("Choose a city from the list.")
        user.city_id = payload.city_id

    if "delivery_slot" in fields and payload.delivery_slot is not None:
        if payload.delivery_slot not in DELIVERY_SLOTS:
            return _error("Choose a delivery time between 06:00 and 09:00 IST.")
        user.delivery_slot = payload.delivery_slot

    if "frequency" in fields and payload.frequency is not None:
        user.frequency = Frequency(payload.frequency)

    if "edition_preference" in fields and payload.edition_preference is not None:
        user.edition_preference = EditionPreference(payload.edition_preference)

    if "genres" in fields and payload.genres is not None:
        session.execute(delete(UserGenre).where(UserGenre.user_id == user.id))
        session.flush()
        for genre in dict.fromkeys(payload.genres):
            session.add(UserGenre(user_id=user.id, genre=genre))

    if "keywords" in fields and payload.keywords is not None:
        session.execute(delete(FollowedKeyword).where(FollowedKeyword.user_id == user.id))
        session.flush()
        for keyword in dict.fromkeys(k.strip().lower() for k in payload.keywords if k.strip()):
            session.add(FollowedKeyword(user_id=user.id, keyword=keyword[:64]))

    session.flush()
    session.refresh(user)
    return _profile(user)


@router.post("/api/me/pause", response_model=MeResponse)
def pause_me(
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    session: Annotated[Session, Depends(db_session)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> JSONResponse | MeResponse:
    user = _load_account(session, user_id)
    if user.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAUSED):
        return _error("Only an active subscription can be paused.")
    if user.status is not SubscriptionStatus.PAUSED:
        user.status = SubscriptionStatus.PAUSED
        user.status_changed_at = now_utc()
    return _profile(user)


@router.post("/api/me/resume", response_model=MeResponse)
def resume_me(
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    session: Annotated[Session, Depends(db_session)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> JSONResponse | MeResponse:
    user = _load_account(session, user_id)
    if user.status not in (SubscriptionStatus.PAUSED, SubscriptionStatus.ACTIVE):
        return _error("Only a paused subscription can be resumed.")
    if user.status is not SubscriptionStatus.ACTIVE:
        user.status = SubscriptionStatus.ACTIVE
        user.status_changed_at = now_utc()
    return _profile(user)


# --------------------------------------------------------------- DPDP rights


@router.get("/api/me/export")
def export_me(
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    session: Annotated[Session, Depends(db_session)],
) -> dict[str, Any]:
    """A machine-readable copy of everything held about the reader."""
    user = _load_account(session, user_id)

    consents = session.scalars(select(Consent).where(Consent.user_id == user.id))
    votes = session.scalars(select(Feedback).where(Feedback.user_id == user.id))
    deliveries = session.scalars(select(Delivery).where(Delivery.user_id == user.id))

    return {
        "profile": {
            "email": user.email,
            "name": user.name,
            "city_id": user.city_id,
            "status": user.status.value,
            "delivery_slot": user.delivery_slot.isoformat(),
            "frequency": user.frequency.value,
            "edition_preference": user.edition_preference.value,
            "language": user.language,
            "age_confirmed": user.age_confirmed,
            "created_at": user.created_at.isoformat(),
        },
        "genres": sorted(genre.genre for genre in user.genres),
        "keywords": sorted(keyword.keyword for keyword in user.keywords),
        "consents": [
            {
                "policy_version": row.policy_version,
                "consented_at": row.consented_at.isoformat(),
                "channel": row.channel,
            }
            for row in consents
        ],
        "feedback": [
            {
                "story_id": str(row.story_id),
                "vote": row.vote.value,
                "created_at": row.created_at.isoformat(),
            }
            for row in votes
        ],
        "deliveries": [
            {
                "edition_date": row.edition_date.isoformat(),
                "type": row.type.value,
                "status": row.status.value,
                "sent_at": row.sent_at.isoformat() if row.sent_at else None,
            }
            for row in deliveries
        ],
    }


@router.post("/api/me/delete")
def delete_me(
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    session: Annotated[Session, Depends(db_session)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> JSONResponse:
    """DPDP erasure: clear personal data, keep the anonymous audit trail.

    The row survives so `deliveries` and `feedback` keep a place to point at
    (their own FKs are ON DELETE SET NULL for the day a retention job removes
    the row outright); what leaves immediately is everything that identifies
    a person. Consent records are kept as required — they no longer name
    anyone once the row above them is anonymised.
    """
    user = _load_account(session, user_id)
    moment = now_utc()

    session.execute(delete(UserGenre).where(UserGenre.user_id == user.id))
    session.execute(delete(FollowedKeyword).where(FollowedKeyword.user_id == user.id))
    session.execute(delete(Token).where(Token.user_id == user.id))

    user.name = "Deleted reader"
    user.email = f"deleted-{user.id}@deleted.invalid"
    user.city_id = None
    user.status = SubscriptionStatus.UNSUBSCRIBED
    user.status_changed_at = moment
    user.anonymised_at = moment

    session.flush()

    response = JSONResponse({"status": "deleted"})
    clear_session(response)
    return response


# ---------------------------------------------------------------- helpers


def _send_login_link(session: Session, user: User, config: Settings) -> None:
    raw = tokens.issue(session, user_id=user.id, purpose=TokenPurpose.MAGIC_LINK)
    base = str(config.base_url).rstrip("/")
    link = f"{base}/login/{raw}"

    Sender(settings=config).send(
        Message(
            to=user.email,
            subject=f"Sign in to {BRAND}",
            html=(
                f"<p>Hello {user.name.split()[0] if user.name.strip() else 'there'},</p>"
                f"<p>Sign in to {BRAND}:</p>"
                f'<p><a href="{link}">Sign in</a></p>'
                "<p>This link expires in 30 minutes. "
                "If you didn't request it, ignore this email.</p>"
            ),
            text=(
                f"Sign in to {BRAND}:\n{link}\n\n"
                "This link expires in 30 minutes. "
                "If you didn't request it, ignore this email."
            ),
        )
    )


def _error(message: str) -> JSONResponse:
    return JSONResponse(
        {"status": "error", "message": message}, status_code=status.HTTP_400_BAD_REQUEST
    )

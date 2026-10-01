"""Reader-facing routes: signup, opt-in, unsubscribe, feedback.

Every emailed link follows the same shape, and it is the shape that matters:

    GET  /thing/{token}   renders a page and changes nothing
    POST /thing/{token}   performs the action

Corporate mail security opens links before the reader does. A GET that
unsubscribed someone would unsubscribe them the moment the mail arrived, and a
GET that recorded a thumbs-up would record it for a machine. The one exception
is the RFC 8058 one-click unsubscribe, which is itself a POST and so is safe.
"""

from __future__ import annotations

import logging
import uuid
from datetime import time as clock_time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api import pages
from app.api.deps import db_session
from app.api.deps import settings as get_request_settings
from app.api.security import RateLimiter, TurnstileError, client_key, verify_turnstile
from app.clock import now_utc
from app.config.loader import load_policy, only_active_genres
from app.config.schemas import GENRE_KEYS, GenreKey
from app.config.settings import Settings
from app.email import tokens
from app.email.sender import Message, Sender
from app.email.tokens import TokenError
from app.models.content import Story
from app.models.editions import Feedback
from app.models.enums import SubscriptionStatus, TokenPurpose, Vote
from app.models.users import (
    DELIVERY_SLOTS as PUBLISHED_SLOTS,
)
from app.models.users import (
    City,
    Consent,
    FollowedKeyword,
    User,
    UserGenre,
    WaitlistEntry,
)
from app.render.email import BRAND

logger = logging.getLogger(__name__)

router = APIRouter()

# Signup is the only unauthenticated write, so it is the one worth limiting.
signup_limiter = RateLimiter(name="signup", limit=5, window_seconds=300)
# Feedback is one click per story, but a scanner can hammer it.
feedback_limiter = RateLimiter(name="feedback", limit=60, window_seconds=60)

# Parsed from the same list the database CHECK constraint is built from.
DELIVERY_SLOTS = tuple(clock_time.fromisoformat(slot) for slot in PUBLISHED_SLOTS)


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    city_id: str = Field(min_length=2, max_length=64)
    genres: list[GenreKey] = Field(min_length=1, max_length=len(GENRE_KEYS))
    delivery_slot: clock_time
    frequency: Literal["daily", "weekdays"] = "daily"
    edition_preference: Literal["india", "global", "mixed"] = "mixed"
    keywords: list[str] = Field(default_factory=list, max_length=10)
    age_confirmed: bool
    turnstile_token: str | None = None

    @field_validator("genres")
    @classmethod
    def _genres_are_offered(cls, genres: list[GenreKey]) -> list[GenreKey]:
        return only_active_genres(genres)


class SignupResponse(BaseModel):
    status: Literal["check_your_email", "waitlisted"]
    message: str


CHECK_EMAIL = "Check your email to confirm your subscription."
WAITLISTED = (
    "We're at capacity today. You're on the waitlist and we'll email you when a place opens."
)


@router.post("/api/signup", response_model=SignupResponse)
async def signup(
    payload: SignupRequest,
    request: Request,
    session: Annotated[Session, Depends(db_session)],
    config: Annotated[Settings, Depends(get_request_settings)],
) -> JSONResponse:
    signup_limiter.enforce(session, client_key(request))

    if not payload.age_confirmed:
        return _error("This service is for readers aged 18 and over.")
    if payload.delivery_slot not in DELIVERY_SLOTS:
        return _error("Choose a delivery time between 06:00 and 09:00 IST.")

    try:
        human = await verify_turnstile(payload.turnstile_token, settings=config)
    except TurnstileError as exc:
        logger.error("turnstile unavailable: %s", exc)
        return _error(
            "We couldn't verify that request. Please try again.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if not human:
        return _error("We couldn't verify that request. Please try again.")

    # Everything below this line talks to Postgres and to Gmail, both of them
    # blocking. This is the only async route in the app, so that work has to
    # leave the event loop rather than stall every other request on it.
    return await run_in_threadpool(_register, session, payload, config)


def _register(session: Session, payload: SignupRequest, config: Settings) -> JSONResponse:
    if session.get(City, payload.city_id) is None:
        return _error("Choose a city from the list.")

    address = payload.email.lower()
    existing = session.scalar(select(User).where(User.email == address))
    if existing is not None:
        # Never reveal whether an address is already subscribed.
        if existing.status is SubscriptionStatus.PENDING:
            _send_opt_in(session, existing, config)
        return _ok("check_your_email", CHECK_EMAIL)

    waitlisted = _active_count(session) >= config.max_active_subscribers
    user = User(
        email=address,
        name=payload.name.strip(),
        city_id=payload.city_id,
        status=SubscriptionStatus.WAITLISTED if waitlisted else SubscriptionStatus.PENDING,
        delivery_slot=payload.delivery_slot,
        frequency=payload.frequency,
        edition_preference=payload.edition_preference,
        age_confirmed=True,
    )
    session.add(user)
    session.flush()

    for genre in dict.fromkeys(payload.genres):
        session.add(UserGenre(user_id=user.id, genre=genre))
    for keyword in dict.fromkeys(k.strip().lower() for k in payload.keywords if k.strip()):
        session.add(FollowedKeyword(user_id=user.id, keyword=keyword[:64]))

    session.add(
        Consent(
            user_id=user.id,
            policy_version=load_policy().version,
            consented_at=now_utc(),
            channel="signup",
        )
    )

    if waitlisted:
        session.add(WaitlistEntry(user_id=user.id))
        session.flush()
        return _ok("waitlisted", WAITLISTED)

    session.flush()
    _send_opt_in(session, user, config)
    return _ok("check_your_email", CHECK_EMAIL)


# ----------------------------------------------------------------- opt-in


@router.get("/opt-in/{token}", response_class=HTMLResponse)
def opt_in_page(token: str) -> HTMLResponse:
    """Renders a button. Confirms nothing — a scanner opened this, perhaps."""
    return pages.confirm(
        title="Confirm your subscription",
        body=(f"Press the button to start receiving {BRAND}. We won't send anything until you do."),
        action=f"/opt-in/{token}",
        label="Confirm my subscription",
    )


@router.post("/opt-in/{token}", response_class=HTMLResponse)
def opt_in_confirm(token: str, session: Annotated[Session, Depends(db_session)]) -> HTMLResponse:
    try:
        stored = tokens.redeem(session, token, TokenPurpose.OPT_IN)
    except TokenError:
        return pages.gone(
            title="That link has expired",
            body="Confirmation links last seven days. Sign up again and we'll send a fresh one.",
        )

    user = session.get(User, stored.user_id) if stored.user_id else None
    if user is None:
        return pages.gone(
            title="That link is no longer valid",
            body="We couldn't find the subscription it belongs to.",
        )

    if user.status is SubscriptionStatus.PENDING:
        user.status = SubscriptionStatus.ACTIVE
        user.status_changed_at = now_utc()

    return pages.done(
        title="You're subscribed",
        body="Your first edition will arrive at your chosen time tomorrow morning.",
    )


# ------------------------------------------------------------ unsubscribe


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_page(token: str) -> HTMLResponse:
    return pages.confirm(
        title="Unsubscribe",
        body="Press the button to stop receiving the newsletter. This takes effect immediately.",
        action=f"/unsubscribe/{token}",
        label="Unsubscribe me",
    )


@router.post("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe(token: str, session: Annotated[Session, Depends(db_session)]) -> HTMLResponse:
    try:
        stored = tokens.redeem(session, token, TokenPurpose.UNSUBSCRIBE)
    except TokenError:
        return pages.gone(
            title="That link is not valid",
            body=(
                "If you're still receiving the newsletter, reply to any "
                "edition and we'll remove you."
            ),
        )

    user = session.get(User, stored.user_id) if stored.user_id else None
    if user is not None and user.status is not SubscriptionStatus.UNSUBSCRIBED:
        user.status = SubscriptionStatus.UNSUBSCRIBED
        user.status_changed_at = now_utc()

    # Unsubscribing twice is not an error, and the page never differs.
    return pages.done(
        title="You've been unsubscribed",
        body="You won't receive any more editions. Thank you for reading.",
    )


# --------------------------------------------------------------- feedback


@router.get("/feedback/{token}", response_class=HTMLResponse)
def feedback_page(token: str) -> HTMLResponse:
    try:
        claims = tokens.verify(token, tokens.FEEDBACK)
    except TokenError:
        return pages.gone(title="That link is not valid", body="We couldn't read that link.")

    vote = "helpful" if claims.extra.get("vote") == Vote.UP.value else "not helpful"
    return pages.confirm(
        title="Send your feedback",
        body=f"Press the button to tell us this story was {vote}.",
        action=f"/feedback/{token}",
        label="Send feedback",
    )


@router.post("/feedback/{token}", response_class=HTMLResponse)
def feedback(
    token: str, request: Request, session: Annotated[Session, Depends(db_session)]
) -> HTMLResponse:
    feedback_limiter.enforce(session, client_key(request))

    try:
        claims = tokens.verify(token, tokens.FEEDBACK)
        story_id = uuid.UUID(claims.subject)
        user_id = uuid.UUID(str(claims.extra["user"]))
        vote = Vote(str(claims.extra["vote"]))
    except (TokenError, KeyError, ValueError):
        return pages.gone(title="That link is not valid", body="We couldn't read that link.")

    if session.get(Story, story_id) is None or session.get(User, user_id) is None:
        return pages.gone(
            title="That link is not valid", body="We couldn't find the story it refers to."
        )

    existing = session.scalar(
        select(Feedback).where(Feedback.user_id == user_id, Feedback.story_id == story_id)
    )
    if existing is None:
        session.add(Feedback(user_id=user_id, story_id=story_id, vote=vote))
    elif existing.vote is not vote:
        # Changing your mind is allowed; it re-enters the next aggregation.
        existing.vote = vote
        existing.aggregated_at = None

    return pages.done(title="Thank you", body="Your feedback helps us choose tomorrow's stories.")


# ---------------------------------------------------------------- helpers


def _active_count(session: Session) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING]))
        )
        or 0
    )


def _send_opt_in(session: Session, user: User, config: Settings) -> None:
    raw = tokens.issue(session, user_id=user.id, purpose=TokenPurpose.OPT_IN)
    base = str(config.base_url).rstrip("/")
    link = f"{base}/opt-in/{raw}"

    Sender(settings=config).send(
        Message(
            to=user.email,
            subject=f"Confirm your {BRAND} subscription",
            html=(
                f"<p>Hello {user.name.split()[0] if user.name.strip() else 'there'},</p>"
                f"<p>Confirm your subscription to {BRAND}:</p>"
                f'<p><a href="{link}">Confirm my subscription</a></p>'
                "<p>If you didn't request this, ignore this email and nothing will happen.</p>"
            ),
            text=(
                f"Confirm your subscription to {BRAND}:\n{link}\n\n"
                "If you didn't request this, ignore this email and nothing will happen."
            ),
        )
    )


def _ok(state: str, message: str) -> JSONResponse:
    return JSONResponse({"status": state, "message": message})


def _error(message: str, code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    return JSONResponse({"status": "error", "message": message}, status_code=code)

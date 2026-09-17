"""Security middleware, bot checks, and rate limiting.

The rule that shapes most of this file is link-scanner safety. Corporate mail
security opens every link in an email before the reader sees it, so a GET that
unsubscribes someone would unsubscribe them the moment the mail arrives. Every
link in an email therefore points at a GET that only *shows* something, with a
button that POSTs.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import httpx
from fastapi import HTTPException, Request, Response, status
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import Settings
from app.models.operations import RateLimitHit

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # The confirm pages are self-contained: no scripts, no external anything.
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


class RateLimiter:
    """Fixed-window request count, shared across every Cloud Run instance
    via the `rate_limit_hits` table (app/models/operations.py), keyed by
    (bucket, key, window_start).

    An atomic upsert (`INSERT ... ON CONFLICT DO UPDATE ... RETURNING`)
    means the count is correct under real concurrent requests, not just
    within one process — the previous in-memory version kept a separate
    count per instance, so the real limit was 5 x N Cloud Run instances.

    Uses the caller's own request-scoped session (`db_session`) rather than
    an independent one, since every call site is a route's first line,
    before anything that could fail: a route whose *own* later write rolls
    back would take an already-recorded hit down with it, but that window
    is deliberately small rather than zero, since an independent session
    is exactly what the test suite's dependency-injected session can't
    accommodate (see `app/llm/recorder.py` for where that trade-off goes
    the other way, in a job context with real settings behind it).
    """

    def __init__(self, *, name: str, limit: int, window_seconds: float) -> None:
        self._name = name
        self._limit = limit
        self._window = window_seconds

    def _window_start(self, moment: datetime) -> datetime:
        epoch = moment.timestamp()
        return datetime.fromtimestamp(epoch - (epoch % self._window), tz=UTC)

    def check(self, session: Session, key: str, *, now: datetime | None = None) -> bool:
        moment = now or datetime.now(UTC)
        window_start = self._window_start(moment)
        statement = (
            insert(RateLimitHit)
            .values(bucket=self._name, key=key, window_start=window_start, count=1)
            .on_conflict_do_update(
                index_elements=["bucket", "key", "window_start"],
                set_={"count": RateLimitHit.count + 1},
            )
            .returning(RateLimitHit.count)
        )
        count = session.execute(statement).scalar_one()
        return count <= self._limit

    def reset(self, session: Session) -> None:
        """Clear this limiter's own rows. Counts are shared across the
        whole database now, so tests need this to isolate one test's
        window from the next, the same as the in-memory version needed it
        to isolate one process's counts from another test run."""
        session.execute(delete(RateLimitHit).where(RateLimitHit.bucket == self._name))

    def enforce(self, session: Session, key: str) -> None:
        if not self.check(session, key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again shortly.",
            )


def client_key(request: Request) -> str:
    """Identify the caller for rate limiting.

    Cloud Run terminates TLS upstream, so the direct peer is a load balancer;
    the first hop in X-Forwarded-For is the closest thing to the caller.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class TurnstileError(Exception):
    """The bot check could not be completed."""


async def verify_turnstile(
    token: str | None, *, settings: Settings, client: httpx.AsyncClient | None = None
) -> bool:
    """Check a Cloudflare Turnstile token.

    Outside prod an unconfigured secret skips the check, so development does
    not need a Cloudflare account. In prod a missing secret is a failure, not
    a skip: silently accepting every signup because a key went missing is
    exactly the outcome this guard exists to prevent.
    """
    secret = settings.turnstile_secret_key
    if secret is None:
        if settings.is_prod:
            raise TurnstileError("TURNSTILE_SECRET_KEY is not configured")
        logger.warning("turnstile check skipped: no secret configured (non-prod)")
        return True

    if not token:
        return False

    owned = client is None
    http = client or httpx.AsyncClient(timeout=10.0)
    try:
        response = await http.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": secret.get_secret_value(), "response": token},
        )
        if response.status_code != httpx.codes.OK:
            raise TurnstileError(f"verification returned HTTP {response.status_code}")
        payload = response.json()
    except httpx.HTTPError as exc:
        raise TurnstileError(f"{type(exc).__name__}: {exc}") from exc
    finally:
        if owned:
            await http.aclose()

    return bool(payload.get("success"))

"""Security middleware, bot checks, and rate limiting.

The rule that shapes most of this file is link-scanner safety. Corporate mail
security opens every link in an email before the reader sees it, so a GET that
unsubscribes someone would unsubscribe them the moment the mail arrives. Every
link in an email therefore points at a GET that only *shows* something, with a
button that POSTs.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable

import httpx
from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import Settings

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
    """Fixed-capacity sliding window, per key.

    In-process, so each Cloud Run instance keeps its own counts and the real
    limit is per instance rather than global. Good enough to blunt a script;
    not a defence against a distributed flood. Recorded in the backlog.
    """

    def __init__(self, *, limit: int, window_seconds: float) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, *, now: float | None = None) -> bool:
        moment = now if now is not None else time.monotonic()
        hits = self._hits.setdefault(key, deque())
        while hits and moment - hits[0] > self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(moment)
        return True

    def reset(self) -> None:
        """Forget every window. Counts are per process, so tests need this."""
        self._hits.clear()

    def enforce(self, key: str) -> None:
        if not self.check(key):
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

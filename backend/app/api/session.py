"""The reader's signed-in session: a cookie, and the CSRF token beside it.

There is no session table. A session is a stateless signed token (the same
mechanism as a feedback link, see `app/email/tokens.py`), carried in an
HttpOnly cookie so page script can never read it. It cannot be revoked before
it expires — there being no row to delete — so it is short-lived and reissued
on every login; logging out simply asks the browser to forget the cookie.

**CSRF:** a cookie is ambient authority — a form on an unrelated site would
ride along with it automatically — so every state-changing request must prove
it was made by the site's own script, not just by the reader's browser. The
double-submit pattern does that without a server-side store: a second,
non-HttpOnly cookie holds the same random value that script must also send as
a header, and only same-origin script can read a cookie to put it there.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from fastapi import HTTPException, Request, Response, status

from app.clock import now_utc
from app.config.settings import Settings
from app.email import tokens
from app.email.tokens import TokenError

SESSION_COOKIE = "session"
CSRF_COOKIE = "csrf"
CSRF_HEADER = "X-CSRF-Token"

SESSION_PURPOSE = "session"
SESSION_TTL = timedelta(days=30)


def issue_session(response: Response, *, user_id: uuid.UUID, settings: Settings) -> None:
    """Set the session and CSRF cookies on a response that logs someone in."""
    session_token = tokens.sign(SESSION_PURPOSE, str(user_id), expires_in=SESSION_TTL)
    csrf_token = secrets.token_urlsafe(24)

    secure = settings.is_prod
    max_age = int(SESSION_TTL.total_seconds())
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
        httponly=False,  # script must read this one to echo it back
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def current_user_id(request: Request) -> uuid.UUID | None:
    """The signed-in user, or None. Never raises: an absent cookie is not an error."""
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    try:
        claims = tokens.verify(raw, SESSION_PURPOSE, now=now_utc())
        return uuid.UUID(claims.subject)
    except (TokenError, ValueError):
        return None


def require_user(request: Request) -> uuid.UUID:
    """FastAPI dependency: the signed-in user, or 401."""
    user_id = current_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required.")
    return user_id


def require_csrf(request: Request) -> None:
    """FastAPI dependency for state-changing routes: the header must match the cookie.

    Both are read fresh on every request, so there is nothing to expire or
    clean up, and a stolen session cookie alone (e.g. via a network log that
    somehow kept it, or a cross-site request that cannot read the non-HttpOnly
    cookie in the first place) is not enough to act.
    """
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Missing or bad CSRF token."
        )

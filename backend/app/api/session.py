"""The reader's signed-in session: a cookie, and the CSRF token beside it.

A session is still a stateless signed token (the same mechanism as a feedback
link, see `app/email/tokens.py`), carried in an HttpOnly cookie so page
script can never read it — but it now carries a `sid` claim naming a row in
`user_sessions` (`app/models/users.py`), so it can be revoked before it
naturally expires. Logout marks that row `revoked_at`; `current_user_id()`
checks it on every request in addition to verifying the signature. This is
one extra indexed lookup per authenticated request — a real cost, but a
negligible one at this project's traffic (ADR 0001), and the reason a stolen
cookie could not previously be killed before its 30-day expiry.

**CSRF:** a cookie is ambient authority — a form on an unrelated site would
ride along with it automatically — so every state-changing request must prove
it was made by the site's own script, not just by the reader's browser. The
double-submit pattern does that without its own server-side store: a second,
non-HttpOnly cookie holds the same random value that script must also send as
a header, and only same-origin script can read a cookie to put it there.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.clock import now_utc
from app.config.settings import Settings
from app.email import tokens
from app.email.tokens import TokenError
from app.models.users import UserSession

SESSION_COOKIE = "session"
CSRF_COOKIE = "csrf"
CSRF_HEADER = "X-CSRF-Token"

SESSION_PURPOSE = "session"
SESSION_TTL = timedelta(days=30)


def issue_session(
    response: Response, *, user_id: uuid.UUID, settings: Settings, session: Session
) -> None:
    """Set the session and CSRF cookies on a response that logs someone in."""
    now = now_utc()
    row = UserSession(user_id=user_id, expires_at=now + SESSION_TTL)
    session.add(row)
    session.flush()  # row.id must exist before it goes into the signed token

    session_token = tokens.sign(
        SESSION_PURPOSE, str(user_id), expires_in=SESSION_TTL, now=now, sid=str(row.id)
    )
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


def clear_session(request: Request, response: Response, session: Session) -> None:
    """Log out: revoke the session row (if the cookie names a real one),
    then ask the browser to forget both cookies either way."""
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        try:
            claims = tokens.verify(raw, SESSION_PURPOSE, now=now_utc())
            sid = claims.extra.get("sid")
            row = session.get(UserSession, uuid.UUID(str(sid))) if sid else None
            if row is not None and row.revoked_at is None:
                row.revoked_at = now_utc()
        except (TokenError, ValueError):
            pass  # already unusable; nothing to revoke

    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def current_user_id(request: Request, session: Session) -> uuid.UUID | None:
    """The signed-in user, or None. Never raises: an absent cookie is not an error."""
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    try:
        claims = tokens.verify(raw, SESSION_PURPOSE, now=now_utc())
        sid = claims.extra.get("sid")
        if sid is None:
            # A token signed before sessions were revocable. Rather than
            # trust the signature alone forever, treat it like any other
            # session this deploy can't vouch for — sign in again.
            return None
        row = session.get(UserSession, uuid.UUID(str(sid)))
        if row is None or row.revoked_at is not None:
            return None
        return uuid.UUID(claims.subject)
    except (TokenError, ValueError):
        return None


def require_user(request: Request, session: Annotated[Session, Depends(db_session)]) -> uuid.UUID:
    """FastAPI dependency: the signed-in user, or 401."""
    user_id = current_user_id(request, session)
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

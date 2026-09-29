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
shape is still double-submit — a second, non-HttpOnly cookie holds a value
script must read and echo back as a header, since only same-origin script
can read a cookie to put it there — but verification now checks the header
against `csrf_secret` on the `user_sessions` row (resolved through the
HttpOnly session cookie), not against the client-supplied CSRF cookie
itself. An attacker who could set cookies on this origin at all (e.g. a
subdomain takeover) used to be able to satisfy both sides by choosing a
matching cookie and header; now the value they'd need to match is never
sent anywhere the client — legitimate or attacker — can read it back from.
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


def _active_session(request: Request, session: Session) -> UserSession | None:
    """The row the session cookie names, if it verifies and isn't revoked.

    Shared by `current_user_id` and `require_csrf`, which independently need
    the same row for different reasons — the user it belongs to, and the
    CSRF secret stored on it.
    """
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
    except (TokenError, ValueError):
        return None
    if row is None or row.revoked_at is not None:
        return None
    return row


def issue_session(
    response: Response, *, user_id: uuid.UUID, settings: Settings, session: Session
) -> None:
    """Set the session and CSRF cookies on a response that logs someone in."""
    now = now_utc()
    csrf_secret = secrets.token_urlsafe(24)
    row = UserSession(user_id=user_id, csrf_secret=csrf_secret, expires_at=now + SESSION_TTL)
    session.add(row)
    session.flush()  # row.id must exist before it goes into the signed token

    session_token = tokens.sign(
        SESSION_PURPOSE, str(user_id), expires_in=SESSION_TTL, now=now, sid=str(row.id)
    )

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
        csrf_secret,
        max_age=max_age,
        httponly=False,  # script must read this one to echo it back
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session(request: Request, response: Response, session: Session) -> None:
    """Log out: revoke the session row (if the cookie names a real one),
    then ask the browser to forget both cookies either way."""
    row = _active_session(request, session)
    if row is not None:
        row.revoked_at = now_utc()

    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def current_user_id(request: Request, session: Session) -> uuid.UUID | None:
    """The signed-in user, or None. Never raises: an absent cookie is not an error."""
    row = _active_session(request, session)
    return row.user_id if row is not None else None


def require_user(request: Request, session: Annotated[Session, Depends(db_session)]) -> uuid.UUID:
    """FastAPI dependency: the signed-in user, or 401."""
    user_id = current_user_id(request, session)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required.")
    return user_id


def require_csrf(request: Request, session: Annotated[Session, Depends(db_session)]) -> None:
    """FastAPI dependency for state-changing routes: the header must match
    the secret stored on the session the request's own cookie names — not
    the client-supplied CSRF cookie (see the module docstring for why)."""
    row = _active_session(request, session)
    header = request.headers.get(CSRF_HEADER)
    if row is None or not header or not secrets.compare_digest(row.csrf_secret, header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Missing or bad CSRF token."
        )

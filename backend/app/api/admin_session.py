"""The admin's signed-in session.

CLAUDE.md: "Admin dashboard: magic-link login restricted to an allowlisted
owner email." There is no admin row anywhere in the schema — only the one
address in `ADMIN_EMAIL` — so this deliberately does not reuse the reader
session in `app/api/session.py`: a subscriber's session token could never
verify against `ADMIN_SESSION_PURPOSE`, and an admin session carries an email
address as its subject, not a user id.

Separate cookie names, not just a separate purpose, matter here too: a
browser used for both a reader's account and the admin dashboard would send
every cookie whose path matches, and two cookies with the same name but
different paths is an ambiguous Cookie header, not a safe combination.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import HTTPException, Request, Response, status

from app.clock import now_utc
from app.config.settings import Settings
from app.email import tokens
from app.email.tokens import TokenError

ADMIN_SESSION_COOKIE = "admin_session"
ADMIN_CSRF_COOKIE = "admin_csrf"
ADMIN_CSRF_HEADER = "X-CSRF-Token"

ADMIN_SESSION_PURPOSE = "admin_session"
# Shorter than a reader's 30 days: admin access is more sensitive, and
# whoever holds ADMIN_EMAIL's inbox can always request another link.
ADMIN_SESSION_TTL = timedelta(hours=12)


def issue_admin_session(response: Response, *, admin_email: str, settings: Settings) -> None:
    session_token = tokens.sign(ADMIN_SESSION_PURPOSE, admin_email, expires_in=ADMIN_SESSION_TTL)
    csrf_token = secrets.token_urlsafe(24)

    secure = settings.is_prod
    max_age = int(ADMIN_SESSION_TTL.total_seconds())
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/admin",
    )
    response.set_cookie(
        ADMIN_CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/admin",
    )


def clear_admin_session(response: Response) -> None:
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/admin")
    response.delete_cookie(ADMIN_CSRF_COOKIE, path="/admin")


def current_admin_email(request: Request) -> str | None:
    raw = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not raw:
        return None
    try:
        claims = tokens.verify(raw, ADMIN_SESSION_PURPOSE, now=now_utc())
        return claims.subject
    except TokenError:
        return None


def require_admin(request: Request) -> str:
    """FastAPI dependency: the signed-in admin's email, or 401."""
    email = current_admin_email(request)
    if email is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required.")
    return email


def require_admin_csrf(request: Request) -> None:
    cookie = request.cookies.get(ADMIN_CSRF_COOKIE)
    header = request.headers.get(ADMIN_CSRF_HEADER)
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Missing or bad CSRF token."
        )

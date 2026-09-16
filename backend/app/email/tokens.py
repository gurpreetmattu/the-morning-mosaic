"""Signed tokens for links in email.

Two mechanisms, as CLAUDE.md specifies:

- **Stateless signed tokens** for feedback and PDF links. These are issued in
  enormous numbers — one per story per reader — so storing a row for each
  would be waste. They carry their own claims and are verified by signature.
- **Stored tokens** for opt-in, magic-link and unsubscribe. These must be
  single-use or revocable, which a signature alone cannot provide.

Only the SHA-256 hash of a stored token is kept. A database leak must not hand
someone a working magic link.

Every token is single-purpose: a feedback token cannot be replayed as a PDF
token, because the purpose is inside the signed payload and checked on verify.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now_utc
from app.config.settings import get_settings
from app.models.enums import TokenPurpose
from app.models.users import Token

# Stateless purposes. Deliberately disjoint from TokenPurpose, which covers
# the stored ones.
FEEDBACK = "feedback"
PDF = "pdf"

DEFAULT_TTL = {
    TokenPurpose.OPT_IN: timedelta(days=7),
    TokenPurpose.MAGIC_LINK: timedelta(minutes=30),
    # Unsubscribe never expires: a link in a two-year-old email must still work.
    TokenPurpose.UNSUBSCRIBE: None,
}

# Clicking unsubscribe twice must not error, so it is not consumed on use.
SINGLE_USE = {TokenPurpose.OPT_IN, TokenPurpose.MAGIC_LINK}


class TokenError(Exception):
    """The token is missing, malformed, expired, used, or for another purpose."""


@dataclass(frozen=True)
class Claims:
    purpose: str
    subject: str
    expires_at: datetime | None
    extra: dict[str, Any]


def _key() -> bytes:
    return get_settings().token_signing_key.get_secret_value().encode("utf-8")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# ------------------------------------------------------------- stateless


def sign(
    purpose: str,
    subject: str,
    *,
    expires_in: timedelta | None = None,
    now: datetime | None = None,
    # Claims must survive a JSON round trip, so only scalars.
    **extra: str | int | bool | None,
) -> str:
    payload: dict[str, Any] = {"p": purpose, "s": subject, **extra}
    if expires_in is not None:
        payload["e"] = int(((now or now_utc()) + expires_in).timestamp())

    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64(hmac.new(_key(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify(token: str, purpose: str, *, now: datetime | None = None) -> Claims:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise TokenError("malformed token") from exc

    expected = _b64(hmac.new(_key(), body.encode("ascii"), hashlib.sha256).digest())
    # Constant time: a timing oracle here would leak the signature byte by byte.
    if not hmac.compare_digest(expected, signature):
        raise TokenError("bad signature")

    try:
        payload = json.loads(_unb64(body))
    except (ValueError, TypeError) as exc:
        raise TokenError("unreadable payload") from exc

    if payload.get("p") != purpose:
        # A feedback token must never work as a PDF token.
        raise TokenError("wrong purpose")

    expires_at = None
    if "e" in payload:
        expires_at = datetime.fromtimestamp(payload["e"], tz=(now or now_utc()).tzinfo)
        if (now or now_utc()) >= expires_at:
            raise TokenError("expired")

    return Claims(
        purpose=payload["p"],
        subject=str(payload.get("s", "")),
        expires_at=expires_at,
        extra={k: v for k, v in payload.items() if k not in {"p", "s", "e"}},
    )


# ---------------------------------------------------------------- stored


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue(
    session: Session,
    *,
    user_id: uuid.UUID | None,
    purpose: TokenPurpose,
    now: datetime | None = None,
) -> str:
    """Create a stored token and return the raw value, which is never stored."""
    raw = secrets.token_urlsafe(32)
    ttl = DEFAULT_TTL[purpose]
    session.add(
        Token(
            user_id=user_id,
            purpose=purpose,
            token_hash=hash_token(raw),
            expires_at=None if ttl is None else (now or now_utc()) + ttl,
        )
    )
    session.flush()
    return raw


def unsubscribe_token(user_id: uuid.UUID) -> str:
    """The reader's unsubscribe value, derived rather than drawn at random.

    Only a token's hash is stored, so a random unsubscribe token could not be
    rebuilt for tomorrow's email — every send would have to issue another row,
    leaving hundreds of live tokens per reader.

    Deriving it from the signing key and the user id keeps the stored row (so
    it can still be revoked by deleting it) while making the same link
    reproducible for every edition, which is what "unsubscribe tokens do not
    expire" actually requires.
    """
    digest = hmac.new(_key(), f"unsubscribe:{user_id}".encode(), hashlib.sha256).digest()
    return _b64(digest)


def ensure_unsubscribe_token(session: Session, user_id: uuid.UUID) -> str:
    """Return the reader's unsubscribe value, recording it the first time."""
    raw = unsubscribe_token(user_id)
    existing = session.scalar(select(Token).where(Token.token_hash == hash_token(raw)))
    if existing is None:
        session.add(
            Token(
                user_id=user_id,
                purpose=TokenPurpose.UNSUBSCRIBE,
                token_hash=hash_token(raw),
                expires_at=None,
            )
        )
        session.flush()
    return raw


def redeem(
    session: Session,
    raw: str,
    purpose: TokenPurpose,
    *,
    now: datetime | None = None,
) -> Token:
    """Check and consume a stored token. Raises TokenError if unusable."""
    moment = now or now_utc()
    token = session.scalar(
        select(Token).where(Token.token_hash == hash_token(raw), Token.purpose == purpose)
    )
    if token is None:
        raise TokenError("unknown token")
    if token.expires_at is not None and moment >= token.expires_at:
        raise TokenError("expired")
    if token.used_at is not None and purpose in SINGLE_USE:
        raise TokenError("already used")

    if purpose in SINGLE_USE:
        token.used_at = moment
        session.flush()
    return token

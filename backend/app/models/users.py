"""Subscribers, their preferences, and the tokens that act on their behalf."""

from __future__ import annotations

import uuid
from datetime import date, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    CreatedAt,
    GenreKeyColumn,
    Instant,
    OptionalInstant,
    UpdatedAt,
    UuidPk,
    genre_check,
    pg_enum,
)
from app.models.enums import (
    EditionPreference,
    Frequency,
    SubscriptionStatus,
    TokenPurpose,
)

# Delivery slots are every 30 minutes from 06:00 to 09:00 IST.
DELIVERY_SLOTS: tuple[str, ...] = (
    "06:00",
    "06:30",
    "07:00",
    "07:30",
    "08:00",
    "08:30",
    "09:00",
)


class City(Base):
    """Seeded from config/cities.yaml; the id is the YAML slug."""

    __tablename__ = "cities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[CreatedAt]

    __table_args__ = (UniqueConstraint("name", "state"),)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UuidPk]
    # Stored lower-cased; the unique index is what prevents duplicate signups.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city_id: Mapped[str | None] = mapped_column(
        ForeignKey("cities.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        pg_enum(SubscriptionStatus, "subscription_status"),
        nullable=False,
        default=SubscriptionStatus.PENDING,
    )
    delivery_slot: Mapped[time] = mapped_column(Time, nullable=False)
    frequency: Mapped[Frequency] = mapped_column(
        pg_enum(Frequency, "frequency"), nullable=False, default=Frequency.DAILY
    )
    edition_preference: Mapped[EditionPreference] = mapped_column(
        pg_enum(EditionPreference, "edition_preference"),
        nullable=False,
        default=EditionPreference.MIXED,
    )
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    age_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status_changed_at: Mapped[OptionalInstant]
    # Set when the user exercises their DPDP deletion right; personal columns
    # are cleared and deliveries/feedback keep pointing at the anonymised row.
    anonymised_at: Mapped[OptionalInstant]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    city: Mapped[City | None] = relationship()
    genres: Mapped[list[UserGenre]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    keywords: Mapped[list[FollowedKeyword]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "delivery_slot >= TIME '06:00' AND delivery_slot <= TIME '09:00' "
            "AND EXTRACT(MINUTE FROM delivery_slot) IN (0, 30) "
            "AND EXTRACT(SECOND FROM delivery_slot) = 0",
            name="slot_is_a_half_hour_between_0600_and_0900",
        ),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )


class UserGenre(Base):
    __tablename__ = "user_genres"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    genre: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[CreatedAt]

    user: Mapped[User] = relationship(back_populates="genres")

    __table_args__ = (genre_check("genre", "genre"),)


class FollowedKeyword(Base):
    __tablename__ = "followed_keywords"

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    keyword: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[CreatedAt]

    user: Mapped[User] = relationship(back_populates="keywords")

    __table_args__ = (
        UniqueConstraint("user_id", "keyword"),
        CheckConstraint("keyword = lower(keyword)", name="keyword_lowercase"),
    )


class Consent(Base):
    """Append-only DPDP consent record. Never updated, never deleted."""

    __tablename__ = "consents"

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    consented_at: Mapped[Instant]
    # Where the consent came from, e.g. "signup" or "preferences".
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[CreatedAt]


class WaitlistEntry(Base):
    """Signups beyond MAX_ACTIVE_SUBSCRIBERS, in arrival order."""

    __tablename__ = "waitlist"

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    invited_at: Mapped[OptionalInstant]
    created_at: Mapped[CreatedAt]


class UserPreference(Base):
    """Per-user topic weighting, aggregated from feedback by the 04:00 job."""

    __tablename__ = "user_preferences"

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    genre: Mapped[GenreKeyColumn]
    topic_tag: Mapped[str] = mapped_column(String(96), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Keys decay to elapsed calendar days rather than to how many times the
    # feedback job happened to run (see app/jobs/feedback.py). Null only for
    # a preference that has never yet been decayed.
    last_decayed_at: Mapped[OptionalInstant]
    updated_at: Mapped[UpdatedAt]

    __table_args__ = (
        UniqueConstraint("user_id", "genre", "topic_tag"),
        genre_check("genre", "genre"),
    )


class Token(Base):
    """Stored so opt-in and magic-link tokens can be single-use and revocable.

    Only the hash is kept: a database leak must not yield usable links.
    Feedback and PDF links are signed and stateless, so they are not here.
    """

    __tablename__ = "tokens"

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    purpose: Mapped[TokenPurpose] = mapped_column(
        pg_enum(TokenPurpose, "token_purpose"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # Null means it never expires, which is only legitimate for unsubscribe.
    expires_at: Mapped[OptionalInstant]
    used_at: Mapped[OptionalInstant]
    created_at: Mapped[CreatedAt]

    __table_args__ = (
        CheckConstraint(
            "expires_at IS NOT NULL OR purpose = 'unsubscribe'",
            name="only_unsubscribe_is_permanent",
        ),
    )


class UserSession(Base):
    """The one row a reader's session cookie needs to be revocable before it
    expires (see `app/api/session.py`). The cookie itself stays a stateless
    signed token — this table only lets it be killed early: its id is
    embedded in the token as the `sid` claim, and `current_user_id()` checks
    this row's `revoked_at` on every request in addition to verifying the
    signature. Logout, and nothing else yet, sets `revoked_at`; a future
    "sign out everywhere" or a security incident could revoke by `user_id`
    without any change here.

    `csrf_secret` is also here, not just in the double-submit cookie: CSRF
    verification checks the header against *this* stored value, resolved
    through the HttpOnly session cookie, rather than against the readable
    CSRF cookie a subdomain-takeover attacker with document.cookie access
    could set to match whatever header they also send. The readable cookie
    still exists — script still needs some way to learn the value to echo
    it back — it just isn't trusted as the source of truth anymore.
    """

    __tablename__ = "user_sessions"

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    csrf_secret: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[CreatedAt]
    expires_at: Mapped[Instant]
    revoked_at: Mapped[OptionalInstant]


class OutageState(Base):
    """Consecutive failed days per user, driving the 'newsletter paused' notice.

    This is a system state, not the user's `paused` subscription status.
    """

    __tablename__ = "outage_state"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    consecutive_failed_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_failed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    paused_notice_sent_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[UpdatedAt]


__all__ = [
    "DELIVERY_SLOTS",
    "City",
    "Consent",
    "FollowedKeyword",
    "OutageState",
    "Token",
    "User",
    "UserGenre",
    "UserPreference",
    "WaitlistEntry",
]

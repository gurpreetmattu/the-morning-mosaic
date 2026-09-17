"""Enumerations stored in the database.

Members are stored by value, so renaming a member is a migration, not a
free rename.
"""

from __future__ import annotations

from enum import StrEnum


class SubscriptionStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
    WAITLISTED = "waitlisted"


class Frequency(StrEnum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"


class EditionPreference(StrEnum):
    INDIA = "india"
    GLOBAL = "global"
    MIXED = "mixed"


class TokenPurpose(StrEnum):
    OPT_IN = "opt_in"
    MAGIC_LINK = "magic_link"
    UNSUBSCRIBE = "unsubscribe"


class StoryStatus(StrEnum):
    DRAFT = "draft"
    VERIFIED = "verified"
    DROPPED = "dropped"
    WITHDRAWN = "withdrawn"


class SentenceRole(StrEnum):
    HEADLINE = "headline"
    SUMMARY = "summary"
    ONE_LINER = "one_liner"
    WHY_THIS_MATTERS = "why_this_matters"


class TagKind(StrEnum):
    TOPIC = "topic"
    ENTITY = "entity"


class ClaimVerdict(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    PARTIAL = "partial"


class CheckMethod(StrEnum):
    LLM = "llm"
    DETERMINISTIC = "deterministic"


class ImageProvider(StrEnum):
    WIKIMEDIA = "wikimedia"
    UNSPLASH = "unsplash"
    PEXELS = "pexels"
    PUBLISHER = "publisher"
    GENRE_DEFAULT = "genre_default"


class ExtraKind(StrEnum):
    QUOTE = "quote"
    ON_THIS_DAY = "on_this_day"
    MARKET = "market"
    SCORE = "score"
    FIXTURE = "fixture"
    MOVIE_RELEASE = "movie_release"
    MUSIC_RELEASE = "music_release"
    GAME_DEAL = "game_deal"
    AI_TOOL = "ai_tool"
    QUIZ = "quiz"


class RevisionReason(StrEnum):
    BUILD = "build"
    LATE_UPDATE = "late_update"
    WITHDRAWAL = "withdrawal"


class SectionStatus(StrEnum):
    OK = "ok"
    QUIET_DAY = "quiet_day"
    FAILED = "failed"


class DeliveryType(StrEnum):
    NEWSLETTER = "newsletter"
    FAILURE_NOTICE = "failure_notice"
    PAUSED_NOTICE = "paused_notice"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class Vote(StrEnum):
    UP = "up"
    DOWN = "down"


class JobName(StrEnum):
    PURGE = "purge"
    FEEDBACK = "feedback"
    BUILD = "build"
    LATE_UPDATE = "late_update"
    DELIVERY = "delivery"
    FAILURE_NOTICE = "failure_notice"
    BOUNCES = "bounces"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEADLINE_MISSED = "deadline_missed"


class CallStatus(StrEnum):
    OK = "ok"
    ERROR = "error"


class NoticeBatchStatus(StrEnum):
    HELD = "held"
    APPROVED = "approved"
    SUPPRESSED = "suppressed"
    EXPIRED = "expired"
    SENT = "sent"

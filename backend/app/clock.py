"""Time handling.

Two rules hold everywhere in this project:

- Instants are stored and compared in UTC, always timezone-aware.
- `edition_date` is the IST calendar date. It is an editorial label, not an
  instant, and is never derived from the server's local timezone.

Relative dates in copy ("yesterday") are computed here, never by a model.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_utc() -> datetime:
    return datetime.now(UTC)


def to_ist(moment: datetime) -> datetime:
    return require_aware(moment).astimezone(IST)


def require_aware(moment: datetime) -> datetime:
    """Reject naive datetimes rather than guessing their zone.

    A naive timestamp from a feed is ambiguous, and assuming UTC would quietly
    shift an article across the 24-hour freshness boundary.
    """
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("naive datetime: the source timezone must be explicit")
    return moment


def edition_date_for(moment: datetime) -> date:
    """The IST calendar date an instant belongs to."""
    return to_ist(moment).date()


def ist_day_bounds(day: date) -> tuple[datetime, datetime]:
    """The UTC instants bounding an IST calendar day, start inclusive."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=IST)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)

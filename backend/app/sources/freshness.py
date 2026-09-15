"""The freshness rule.

CLAUDE.md: daily stories need a reliable published_at within 24 hours before
the build, IST-normalised; articles without timestamps are dropped.

Enforced here in code rather than described in a prompt, so no model can talk
its way past it.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.clock import require_aware
from app.sources.schemas import DropReason

FRESHNESS_WINDOW = timedelta(hours=24)

# Publisher clocks drift and some backdate to the edition. A little slack
# prevents discarding genuinely new stories; beyond it, a future timestamp
# means the feed is wrong and the item cannot be trusted to be fresh.
MAX_CLOCK_SKEW = timedelta(hours=2)


def freshness_verdict(
    published_at: datetime | None,
    *,
    now: datetime,
    window: timedelta = FRESHNESS_WINDOW,
) -> DropReason | None:
    """None when the item is fresh, otherwise why it must be dropped."""
    if published_at is None:
        return DropReason.NO_TIMESTAMP

    published = require_aware(published_at)
    reference = require_aware(now)

    if published > reference + MAX_CLOCK_SKEW:
        return DropReason.FUTURE_DATED
    if published < reference - window:
        return DropReason.TOO_OLD
    return None

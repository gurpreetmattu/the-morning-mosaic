"""RSS/Atom parsing into FeedItems."""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo

import feedparser

from app.config.schemas import GenreKey
from app.sources.schemas import FeedItem


def _timestamp(entry: Mapping[str, Any], *, fallback_timezone: str | None) -> datetime | None:
    """The entry's publication instant, or None if it has no reliable one.

    feedparser normalises parsed times to UTC. `published` is preferred over
    `updated`: a later edit must not make a stale story look fresh.
    """
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)

    if fallback_timezone is None:
        return None

    # feedparser only sets `*_parsed` when it recognises the date format.
    # A pubDate with no timezone offset (RBI's, so far — a real value, just
    # missing the offset RFC 822 requires) fails that, but the raw string is
    # still usable with this source's own known timezone (config/sources.yaml's
    # `fallback_timezone`, set only when that is actually known) rather than
    # dropping the item outright.
    for field in ("published", "updated"):
        raw = entry.get(field)
        if not raw:
            continue
        try:
            candidate = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            continue
        if candidate.tzinfo is not None:
            # Already has an offset — feedparser would have parsed this via
            # `*_parsed` above, so something else about it is unrecognised.
            # Not this fallback's problem to guess at.
            continue
        return candidate.replace(tzinfo=ZoneInfo(fallback_timezone)).astimezone(UTC)
    return None


def parse_feed(
    content: bytes | str,
    *,
    source_key: str,
    genre: GenreKey,
    fallback_timezone: str | None = None,
) -> list[FeedItem]:
    parsed = feedparser.parse(content)
    items: list[FeedItem] = []
    for entry in parsed.entries:
        link = (entry.get("link") or "").strip()
        title = (entry.get("title") or "").strip()
        if not link or not title:
            # Without both there is nothing to fetch or attribute.
            continue
        items.append(
            FeedItem(
                source_key=source_key,
                genre=genre,
                url=link,
                title=title,
                published_at=_timestamp(entry, fallback_timezone=fallback_timezone),
            )
        )
    return items

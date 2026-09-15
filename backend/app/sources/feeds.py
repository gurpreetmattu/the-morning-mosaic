"""RSS/Atom parsing into FeedItems."""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import feedparser

from app.config.schemas import GenreKey
from app.sources.schemas import FeedItem


def _timestamp(entry: Mapping[str, Any]) -> datetime | None:
    """The entry's publication instant, or None if it has no reliable one.

    feedparser normalises parsed times to UTC. `published` is preferred over
    `updated`: a later edit must not make a stale story look fresh.
    """
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)
    return None


def parse_feed(content: bytes | str, *, source_key: str, genre: GenreKey) -> list[FeedItem]:
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
                published_at=_timestamp(entry),
            )
        )
    return items

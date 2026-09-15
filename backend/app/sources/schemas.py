"""Collector inputs and outputs.

Everything the Collector produces is a Pydantic model, so the Ranker and
Writer receive validated data and the agent is testable without network.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.config.schemas import GenreKey


class DropReason(StrEnum):
    """Why a candidate never became an article.

    Recorded rather than discarded: a sharp change in the mix is the earliest
    signal that a source has changed its markup, its feed, or its terms.
    """

    NO_TIMESTAMP = "no_timestamp"
    TOO_OLD = "too_old"
    FUTURE_DATED = "future_dated"
    ROBOTS_DISALLOWED = "robots_disallowed"
    FEED_FAILED = "feed_failed"
    FETCH_FAILED = "fetch_failed"
    EXTRACTION_FAILED = "extraction_failed"
    TOO_SHORT = "too_short"
    DUPLICATE_URL = "duplicate_url"
    DUPLICATE_CONTENT = "duplicate_content"


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FeedItem(Base):
    """One entry as it appeared in a feed, before the article is fetched."""

    source_key: str
    genre: GenreKey
    url: str
    title: str
    # None is meaningful: an item without a reliable timestamp is dropped.
    published_at: datetime | None = None


class Passage(Base):
    """A numbered chunk of article text. Citations reference these ids."""

    ordinal: int = Field(ge=1)
    text: str = Field(min_length=1)

    @property
    def citation_id(self) -> str:
        return f"p{self.ordinal}"


class CollectedArticle(Base):
    source_key: str
    genre: GenreKey
    url: str
    canonical_url: str | None = None
    title: str
    author: str | None = None
    published_at: datetime
    fetched_at: datetime
    text: str
    passages: list[Passage] = Field(min_length=1)
    content_hash: str


class Dropped(Base):
    url: str
    source_key: str
    reason: DropReason
    detail: str | None = None


class CollectionResult(Base):
    genre: GenreKey
    articles: list[CollectedArticle] = Field(default_factory=list)
    dropped: list[Dropped] = Field(default_factory=list)

    def reason_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.dropped:
            counts[item.reason] = counts.get(item.reason, 0) + 1
        return counts

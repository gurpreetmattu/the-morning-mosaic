"""Ranker inputs and outputs — the verified story pool."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.config.schemas import GenreKey
from app.sources.schemas import CollectedArticle


class Corroboration(StrEnum):
    """How well supported a cluster is, by source count and tier."""

    # At least one tier-1 source: a wire service, official body, or primary
    # document. Sufficient on its own, per CLAUDE.md.
    PRIMARY_OFFICIAL = "primary_official"
    # Two or more independent tier-1/2 sources.
    CORROBORATED = "corroborated"
    # A single established outlet.
    SINGLE_SOURCE = "single_source"
    # Only tier-3 (entertainment/gossip) coverage. Must be hedged.
    TIER3_ONLY = "tier3_only"


class PoolDropReason(StrEnum):
    INSUFFICIENT_CORROBORATION = "insufficient_corroboration"
    BELOW_POOL_CAP = "below_pool_cap"


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PooledStory(Base):
    """One clustered event, ranked, ready for the Writer."""

    # Internal label from clustering. Never published; the Writer writes the
    # headline from the passages.
    event_label: str
    articles: list[CollectedArticle] = Field(min_length=1)
    corroboration: Corroboration
    # Tier-3-only stories must use hedged language ("reportedly").
    hedged: bool
    score: float
    rank: int = Field(ge=1)

    @property
    def source_keys(self) -> list[str]:
        return sorted({article.source_key for article in self.articles})

    @property
    def latest_published_at(self) -> datetime:
        return max(article.published_at for article in self.articles)


class PoolDropped(Base):
    event_label: str
    source_keys: list[str]
    reason: PoolDropReason


class StoryPool(Base):
    genre: GenreKey
    stories: list[PooledStory] = Field(default_factory=list)
    dropped: list[PoolDropped] = Field(default_factory=list)
    # True when clustering fell back to the deterministic path because the
    # model was unavailable or returned nothing usable.
    used_fallback_clustering: bool = False

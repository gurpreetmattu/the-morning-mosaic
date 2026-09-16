"""Ranker inputs and outputs — the verified story pool."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.config.schemas import GenreKey
from app.models.enums import CheckMethod, ClaimVerdict
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


# --------------------------------------------------------------------- writer


class WriterIssue(StrEnum):
    """Why a piece of the Writer's output was rejected or removed.

    Fatal issues drop the story. The rest remove only the offending element,
    per CLAUDE.md: "if only an optional element fails ... drop just that
    element".
    """

    # Fatal — the core of the story cannot be trusted.
    UNPARSEABLE = "unparseable"
    EMPTY_HEADLINE = "empty_headline"
    EMPTY_SUMMARY = "empty_summary"
    UNKNOWN_CITATION = "unknown_citation"
    MISSING_CITATION = "missing_citation"
    COPIED_TEXT = "copied_text"
    MISSING_HEDGE = "missing_hedge"

    # Recoverable — the element is dropped, the story survives.
    DROPPED_ONE_LINER = "dropped_one_liner"
    DROPPED_WHY_THIS_MATTERS = "dropped_why_this_matters"
    DROPPED_TOPIC_TAG = "dropped_topic_tag"
    DROPPED_ENTITY_TAG = "dropped_entity_tag"


class PassageRef(Base):
    """One citable passage, addressed as "a1:p3" within a story."""

    citation_id: str
    article_index: int
    source_key: str
    url: str
    text: str


class DraftSentence(Base):
    text: str = Field(min_length=1)
    passage_ids: list[str] = Field(default_factory=list)


class WrittenStory(Base):
    """Validated Writer output. Everything here is cited and checked."""

    headline: DraftSentence
    summary: list[DraftSentence] = Field(min_length=1)
    # Optional: dropped rather than invented when it fails validation.
    one_liner: DraftSentence | None = None
    why_this_matters: list[DraftSentence] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    entity_tags: list[str] = Field(default_factory=list)
    # Computed in code from the passages, never taken from the model.
    india_relevance: bool = False
    hedged: bool = False

    def sentences(self) -> list[DraftSentence]:
        parts = [self.headline, *self.summary, *self.why_this_matters]
        if self.one_liner is not None:
            parts.append(self.one_liner)
        return parts


class WriterProblem(Base):
    issue: WriterIssue
    detail: str


class WriterResult(Base):
    """A written story, or nothing plus the reasons why."""

    story: WrittenStory | None = None
    problems: list[WriterProblem] = Field(default_factory=list)

    @property
    def dropped(self) -> bool:
        return self.story is None


# --------------------------------------------------------------- fact-checker


class CheckFinding(Base):
    """One verified claim. Recorded whether it passed or failed."""

    element: str
    claim: str
    verdict: ClaimVerdict
    method: CheckMethod
    detail: str = ""

    @property
    def failed(self) -> bool:
        # "partial" is treated as a failure: a half-supported claim published
        # as fact is exactly the error this project refuses to make.
        return self.verdict is not ClaimVerdict.SUPPORTED


class CheckResult(Base):
    """The outcome of verifying one written story."""

    # The story as it survives verification: optional elements that failed are
    # removed. None when the headline or summary could not be verified.
    story: WrittenStory | None = None
    findings: list[CheckFinding] = Field(default_factory=list)
    # Populated when the Writer should try again, naming what to fix.
    feedback: str | None = None

    @property
    def passed(self) -> bool:
        return self.story is not None and self.feedback is None

    def failures(self) -> list[CheckFinding]:
        return [finding for finding in self.findings if finding.failed]


class VerifiedStory(Base):
    """A story that survived the write-and-verify loop."""

    story: WrittenStory
    findings: list[CheckFinding] = Field(default_factory=list)
    attempts: int = Field(ge=1)


class VerificationOutcome(Base):
    verified: VerifiedStory | None = None
    attempts: int = Field(ge=1)
    # Why it was abandoned, when it was.
    reason: str | None = None

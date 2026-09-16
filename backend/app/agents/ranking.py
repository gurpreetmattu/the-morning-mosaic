"""Corroboration and scoring — deterministic, no LLM.

Scoring deliberately uses only three signals: how many independent sources
carried the story, the best source tier, and how recent it is. None of them
can encode which side a story favours, which is how CLAUDE.md's political
balance rule ("ranking must not favor a story because of which side it
favors") is satisfied by construction rather than by instruction.

Clustering is proposed by a model, but every grouping it returns is reconciled
against the real article set here before it is used.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime

from app.agents.schemas import Corroboration
from app.sources.schemas import CollectedArticle

# Credibility tiers, from config/sources.yaml.
TIER_PRIMARY = 1
TIER_ESTABLISHED = 2

FRESHNESS_HOURS = 24.0

# Weights. Breadth dominates, then tier, then recency as a tie-shaper.
BREADTH_CAP = 4
TIER_BONUS = {1: 2.0, 2: 1.0, 3: 0.0}
RECENCY_WEIGHT = 1.5

_WORD = re.compile(r"[a-z0-9]+")

# Dropped before comparing headlines: they carry no topical signal.
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "with",
        "after",
        "over",
        "into",
        "new",
        "says",
        "said",
        "will",
        "amid",
        "ahead",
        "about",
    ]
)

TITLE_SIMILARITY_THRESHOLD = 0.5


def title_tokens(title: str) -> frozenset[str]:
    return frozenset(w for w in _WORD.findall(title.lower()) if w not in _STOPWORDS and len(w) > 2)


def title_similarity(left: str, right: str) -> float:
    a, b = title_tokens(left), title_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster_by_title(
    articles: Mapping[str, CollectedArticle],
    *,
    threshold: float = TITLE_SIMILARITY_THRESHOLD,
) -> list[list[str]]:
    """Deterministic fallback clustering by headline overlap.

    Used when the model is unavailable. Cruder than the model, but it never
    invents a grouping, and a duplicated story is a quality problem rather
    than a factual one.
    """
    clusters: list[list[str]] = []
    for article_id, article in articles.items():
        for cluster in clusters:
            representative = articles[cluster[0]].title
            if title_similarity(representative, article.title) >= threshold:
                cluster.append(article_id)
                break
        else:
            clusters.append([article_id])
    return clusters


def reconcile_clusters(
    proposed: Sequence[Sequence[str]],
    articles: Mapping[str, CollectedArticle],
) -> list[list[str]]:
    """Force a model's proposed grouping to be a valid partition.

    Ids it invented are discarded, an article assigned twice keeps its first
    placement, and anything it forgot becomes its own cluster. The model can
    therefore only influence grouping, never the article set.
    """
    assigned: set[str] = set()
    clusters: list[list[str]] = []

    for group in proposed:
        members = [
            article_id
            for article_id in dict.fromkeys(group)
            if article_id in articles and article_id not in assigned
        ]
        if not members:
            continue
        assigned.update(members)
        clusters.append(members)

    clusters.extend([article_id] for article_id in articles if article_id not in assigned)
    return clusters


def independent_sources(articles: Sequence[CollectedArticle], tiers: Mapping[str, int]) -> int:
    """Count distinct tier-1/2 sources.

    "Independent" means a distinct whitelisted source. Two outlets running the
    same wire copy are not truly independent; identical text is already caught
    by the Collector's content hash, but a lightly rewritten syndication is
    not. Treat this as an upper bound on independence.
    """
    return len(
        {
            article.source_key
            for article in articles
            if tiers.get(article.source_key, 3) <= TIER_ESTABLISHED
        }
    )


def best_tier(articles: Sequence[CollectedArticle], tiers: Mapping[str, int]) -> int:
    return min((tiers.get(article.source_key, 3) for article in articles), default=3)


def corroboration_for(
    articles: Sequence[CollectedArticle], tiers: Mapping[str, int]
) -> Corroboration:
    if best_tier(articles, tiers) == TIER_PRIMARY:
        return Corroboration.PRIMARY_OFFICIAL
    if independent_sources(articles, tiers) >= 2:
        return Corroboration.CORROBORATED
    if independent_sources(articles, tiers) == 1:
        return Corroboration.SINGLE_SOURCE
    return Corroboration.TIER3_ONLY


def meets_gate(corroboration: Corroboration, *, strict: bool) -> bool:
    """Strict genres (india, politics, business) need real corroboration."""
    if not strict:
        return True
    return corroboration in (Corroboration.PRIMARY_OFFICIAL, Corroboration.CORROBORATED)


def score_cluster(
    articles: Sequence[CollectedArticle],
    tiers: Mapping[str, int],
    *,
    now: datetime,
) -> float:
    breadth = float(min(independent_sources(articles, tiers), BREADTH_CAP))
    tier = TIER_BONUS.get(best_tier(articles, tiers), 0.0)

    newest = max(article.published_at for article in articles)
    age_hours = max((now - newest).total_seconds() / 3600.0, 0.0)
    recency = max(0.0, 1.0 - age_hours / FRESHNESS_HOURS) * RECENCY_WEIGHT

    return breadth + tier + recency

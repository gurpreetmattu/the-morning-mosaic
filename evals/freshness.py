"""Freshness: story age at send.

CLAUDE.md: "daily stories need a reliable published_at within 24 hours
before the build." That rule is already enforced deterministically in
`app.sources.freshness` and covered by its own unit tests; what an eval
adds is a number — how close to the 24-hour edge the pool actually runs on
a representative day — which is what CLAUDE.md means by measuring
"freshness (story age at send)" rather than just gating it.

Runs against synthetic fixture articles rather than a live build, so it
needs no database and no LLM; the moment a real edition exists, the same
scoring function can run against actual collected articles instead.
"""

from __future__ import annotations

from app.sources.freshness import FRESHNESS_WINDOW
from app.sources.schemas import CollectedArticle
from evals.datasets.articles import BUILD_TIME, fresh_and_stale_articles
from evals.schemas import CaseResult, EvalResult, EvalStatus

# Every article in the pool must be within the hard rule; there is no
# partial credit for "mostly fresh."
THRESHOLD = 1.0


def age_hours(article: CollectedArticle) -> float:
    return (BUILD_TIME - article.published_at).total_seconds() / 3600


def run() -> EvalResult:
    articles = fresh_and_stale_articles()
    limit_hours = FRESHNESS_WINDOW.total_seconds() / 3600

    cases: list[CaseResult] = []
    for article in articles:
        age = age_hours(article)
        cases.append(
            CaseResult(
                name=article.url,
                passed=age <= limit_hours,
                detail=f"{age:.1f}h old (limit {limit_hours:.0f}h)",
            )
        )

    ages = [age_hours(a) for a in articles]
    score = sum(1 for c in cases if c.passed) / len(cases)
    return EvalResult(
        name="freshness",
        status=EvalStatus.PASSED if score >= THRESHOLD else EvalStatus.FAILED,
        score=score,
        threshold=THRESHOLD,
        detail=(
            f"age at send: mean {sum(ages) / len(ages):.1f}h, "
            f"median {sorted(ages)[len(ages) // 2]:.1f}h, max {max(ages):.1f}h"
        ),
        cases=cases,
    )

"""Groundedness: share of claims supported.

CLAUDE.md's non-negotiable principle, as a number: run the real Writer and
Fact-checker over fixture pooled stories, then measure what fraction of the
claims the Fact-checker actually evaluated came back SUPPORTED rather than
UNSUPPORTED or PARTIAL (which counts as a failure — see
`CheckFinding.failed`: "a half-supported claim published as fact is exactly
the error this project refuses to make").

Needs a live model for both agents, so it's skipped when the gateway is
unreachable — there is no deterministic tier here the way there is for
fact-checker catch rate, because a share-of-claims-supported score is
meaningless without the model actually writing and checking something.
"""

from __future__ import annotations

from app.agents.fact_checker import FactChecker
from app.agents.writer import Writer
from app.agents.writing import build_passages
from app.llm.client import LlmClient
from evals.datasets.pooled_stories import pooled_stories
from evals.schemas import CaseResult, EvalResult, EvalStatus

THRESHOLD = 0.9


def run(llm: LlmClient) -> EvalResult:
    writer = Writer(llm=llm)
    checker = FactChecker(llm=llm)

    cases: list[CaseResult] = []
    supported = 0
    total = 0

    for genre, story in pooled_stories():
        result = writer.write(story, genre)
        if result.story is None:
            cases.append(
                CaseResult(
                    name=story.event_label,
                    passed=False,
                    detail=f"Writer produced nothing: {[p.detail for p in result.problems]}",
                )
            )
            continue

        passages = build_passages(story.articles)
        check = checker.check(result.story, passages)
        for finding in check.findings:
            total += 1
            if not finding.failed:
                supported += 1

        cases.append(
            CaseResult(
                name=story.event_label,
                passed=check.passed,
                detail=f"{len(check.failures())} of {len(check.findings)} claims failed",
            )
        )

    if total == 0:
        return EvalResult(
            name="groundedness",
            status=EvalStatus.FAILED,
            score=0.0,
            threshold=THRESHOLD,
            detail="no claims were produced to score — every fixture story failed to write",
            cases=cases,
        )

    score = supported / total
    return EvalResult(
        name="groundedness",
        status=EvalStatus.PASSED if score >= THRESHOLD else EvalStatus.FAILED,
        score=score,
        threshold=THRESHOLD,
        detail=f"{supported}/{total} claims supported across {len(cases)} fixture stories",
        cases=cases,
    )

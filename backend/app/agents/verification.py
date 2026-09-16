"""The write-and-verify loop.

CLAUDE.md: "Unsupported claim -> back to Writer with the specific error. Max 2
retries. If the core headline/summary still fails, drop the story."

The Writer and Fact-checker know nothing about each other; this joins them.
Feedback is the Fact-checker's own wording, naming the element and what is
missing, rather than a generic "try again" — re-running an identical prompt
and hoping is not a retry strategy.
"""

from __future__ import annotations

from app.agents.fact_checker import FactChecker
from app.agents.schemas import (
    PooledStory,
    VerificationOutcome,
    VerifiedStory,
    WriterProblem,
)
from app.agents.writer import Writer
from app.agents.writing import build_passages
from app.config.schemas import GenreKey

MAX_RETRIES = 2


def write_and_verify(
    *,
    writer: Writer,
    checker: FactChecker,
    pooled: PooledStory,
    genre: GenreKey,
    max_retries: int = MAX_RETRIES,
) -> VerificationOutcome:
    passages = build_passages(pooled.articles)
    feedback: str | None = None
    attempt = 0

    # One initial attempt plus `max_retries` further attempts.
    for attempt in range(1, max_retries + 2):
        written = writer.write(pooled, genre, feedback=feedback)
        if written.story is None:
            feedback = _problems_as_feedback(written.problems)
            continue

        checked = checker.check(written.story, passages)
        if checked.story is not None and checked.feedback is None:
            return VerificationOutcome(
                verified=VerifiedStory(
                    story=checked.story,
                    articles=list(pooled.articles),
                    pool_rank=pooled.rank,
                    findings=checked.findings,
                    attempts=attempt,
                ),
                attempts=attempt,
            )
        feedback = checked.feedback or _problems_as_feedback(written.problems)

    return VerificationOutcome(
        verified=None,
        attempts=attempt,
        reason=feedback or "no verifiable story after all attempts",
    )


def _problems_as_feedback(problems: list[WriterProblem]) -> str:
    return "\n".join(f"- {problem.issue.value}: {problem.detail}" for problem in problems)

"""Shared result types every eval reports through, so `run.py` can print
and threshold-gate them uniformly regardless of what each one measures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EvalStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    # The eval is fully built and ready, but a dependency it genuinely
    # needs (today: the LLM gateway) is unavailable. Not a failure: nothing
    # about the code under test has been shown to be wrong.
    SKIPPED = "skipped"


@dataclass(frozen=True)
class CaseResult:
    """One example within an eval (one planted-error variant, one article
    pair, one story) — the unit `--verbose` prints and a failure names."""

    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class EvalResult:
    """One eval's outcome: a score against a threshold, or a skip reason."""

    name: str
    status: EvalStatus
    # 0.0-1.0. None when status is SKIPPED — there is no score to show.
    score: float | None = None
    threshold: float | None = None
    detail: str = ""
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def failing_cases(self) -> list[CaseResult]:
        return [case for case in self.cases if not case.passed]

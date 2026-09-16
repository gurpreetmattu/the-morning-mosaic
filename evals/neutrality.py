"""Political neutrality checks.

CLAUDE.md: "politics sources span the spectrum; neutral wording, no opinion
or loaded adjectives; ranking must not favor a story because of which side
it favors." This eval covers the wording half only — a deterministic scan
for loaded, opinion-signalling language — because it's the half a fixture
of published text can actually measure. Source-spectrum balance is a
curation property of config/sources.yaml (which outlets are whitelisted for
the politics genre), not something derivable from any one story's text, and
"ranking must not favor a side" is a property of the Ranker's scoring code
(app/agents/ranking.py:score_cluster), already argument-free of any
political signal by construction — there is nothing in its inputs (source
tier, recency, corroboration) that encodes which side a story favors.

The word list is deliberately small and blunt: it exists to catch the
Writer producing op-ed language, not to police every possible bias. A
model that starts hedging around this list rather than writing plainly
would be a prompt problem this eval couldn't see either way.
"""

from __future__ import annotations

import re

from evals.datasets.writer_outputs import neutrality_cases
from evals.schemas import CaseResult, EvalResult, EvalStatus

THRESHOLD = 1.0

# Adjectives and framing that assert a judgement rather than report a fact.
# Not exhaustive — see the module docstring.
_LOADED_WORDS = frozenset(
    [
        "shameful",
        "disastrous",
        "outrage",
        "outrageous",
        "reckless",
        "betrayal",
        "brilliant",
        "heroic",
        "landslide",
        "crushing",
        "hapless",
        "incompetent",
        "corrupt",
        "radical",
        "extremist",
        "failed miserably",
        "disgraceful",
        "triumphant",
    ]
)

_WORD = re.compile(r"[a-z]+(?:\s[a-z]+)?")


def loaded_terms(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(word for word in _LOADED_WORDS if re.search(rf"\b{re.escape(word)}\b", lowered))


def run() -> EvalResult:
    cases: list[CaseResult] = []

    for case in neutrality_cases():
        found = loaded_terms(case.text)
        is_neutral = not found
        correct = is_neutral == case.expected_neutral
        cases.append(
            CaseResult(
                name=case.name,
                passed=correct,
                detail=f"loaded terms found: {found}" if found else "no loaded terms found",
            )
        )

    score = sum(1 for c in cases if c.passed) / len(cases)
    return EvalResult(
        name="neutrality",
        status=EvalStatus.PASSED if score >= THRESHOLD else EvalStatus.FAILED,
        score=score,
        threshold=THRESHOLD,
        detail=f"{len(cases)} fixture passages; heuristic wording scan only (see module docstring)",
        cases=cases,
    )

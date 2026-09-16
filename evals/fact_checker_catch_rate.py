"""Fact-checker catch rate on planted errors.

Was, per docs/BACKLOG.md, "measured by hand, not by an eval": a live run
once caught 6 of 6 planted errors with the control passing, in a scratchpad
script. This is that made permanent and rerunnable.

Two tiers, because the checker itself is two independent things (see
app/agents/fact_checker.py's own docstring):

- The deterministic tier (`unsupported_facts`) needs no LLM and is scored
  against the four planted-error categories it is actually responsible
  for, plus the control. Always runs.
- The full pipeline (`FactChecker.check`, deterministic + the model's
  claim verdicts) is scored against every case, since a working checker
  should catch all seven categories, not just the four the code alone can.
  Skipped when the LLM gateway is unreachable — see llm_probe.py for why
  this can't just call FactChecker anyway and report whatever comes back:
  it fails closed when the model is unreachable, which would silently
  score the control as "correctly caught" too.
"""

from __future__ import annotations

from app.agents.checking import story_elements, unsupported_facts
from app.agents.fact_checker import FactChecker
from app.agents.schemas import PassageRef, WrittenStory
from app.llm.client import LlmClient
from evals.datasets.fact_check_cases import build_story, fact_check_cases
from evals.schemas import CaseResult, EvalResult, EvalStatus

DETERMINISTIC_THRESHOLD = 1.0
FULL_PIPELINE_THRESHOLD = 1.0


def _deterministically_flagged(story: WrittenStory, passages: dict[str, PassageRef]) -> bool:
    texts = {cid: ref.text for cid, ref in passages.items()}
    for _element, sentence in story_elements(story):
        cited = [texts[pid] for pid in sentence.passage_ids if pid in texts]
        if unsupported_facts(sentence.text, cited):
            return True
    return False


def run_deterministic_tier() -> EvalResult:
    cases = [case for case in fact_check_cases() if not case.requires_llm]
    results: list[CaseResult] = []

    for case in cases:
        story, passages = build_story(case)
        flagged = _deterministically_flagged(story, passages)
        correct = flagged == case.should_be_flagged
        results.append(
            CaseResult(
                name=case.name,
                passed=correct,
                detail=f"{case.error_type}: flagged={flagged}, expected={case.should_be_flagged}",
            )
        )

    score = sum(1 for r in results if r.passed) / len(results)
    return EvalResult(
        name="fact_checker_catch_rate.deterministic",
        status=EvalStatus.PASSED if score >= DETERMINISTIC_THRESHOLD else EvalStatus.FAILED,
        score=score,
        threshold=DETERMINISTIC_THRESHOLD,
        detail=(
            f"{len(cases)} cases: control + "
            "wrong_figure/wrong_day/wrong_person/invented_fact_numeric"
        ),
        cases=results,
    )


def run_full_pipeline(llm: LlmClient) -> EvalResult:
    checker = FactChecker(llm=llm)
    cases = fact_check_cases()
    results: list[CaseResult] = []

    for case in cases:
        story, passages = build_story(case)
        result = checker.check(story, passages)
        # A control should pass whole; anything else should fail (its
        # headline/summary is the only element, so any failure is fatal).
        expected_pass = not case.should_be_flagged
        correct = result.passed == expected_pass
        results.append(
            CaseResult(
                name=case.name,
                passed=correct,
                detail=(
                    f"{case.error_type}: passed={result.passed}, expected_pass={expected_pass}, "
                    f"findings={[f.detail for f in result.failures()]}"
                ),
            )
        )

    score = sum(1 for r in results if r.passed) / len(results)
    return EvalResult(
        name="fact_checker_catch_rate.full_pipeline",
        status=EvalStatus.PASSED if score >= FULL_PIPELINE_THRESHOLD else EvalStatus.FAILED,
        score=score,
        threshold=FULL_PIPELINE_THRESHOLD,
        detail=f"{len(cases)} cases: all seven planted-error categories plus two controls",
        cases=results,
    )

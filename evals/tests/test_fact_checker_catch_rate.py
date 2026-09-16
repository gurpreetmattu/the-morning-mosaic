"""The deterministic tier is real, always-runnable code — test it as such,
not just by trusting the eval's own self-report."""

from __future__ import annotations

from evals.datasets.fact_check_cases import build_story, fact_check_cases
from evals.fact_checker_catch_rate import _deterministically_flagged, run_deterministic_tier
from evals.schemas import EvalStatus


def test_every_case_has_a_unique_name() -> None:
    names = [case.name for case in fact_check_cases()]
    assert len(names) == len(set(names))


def test_controls_are_not_flagged_and_errors_are() -> None:
    for case in fact_check_cases():
        if case.requires_llm:
            continue  # covered by the full-pipeline eval, which needs a live model
        story, passages = build_story(case)
        flagged = _deterministically_flagged(story, passages)
        assert flagged == case.should_be_flagged, case.name


def test_the_deterministic_tier_passes_at_its_own_threshold() -> None:
    result = run_deterministic_tier()

    assert result.status is EvalStatus.PASSED
    assert result.score == 1.0
    assert result.failing_cases == []


def test_llm_required_cases_are_excluded_from_the_deterministic_tier() -> None:
    result = run_deterministic_tier()
    scored_names = {case.name for case in result.cases}

    for case in fact_check_cases():
        if case.requires_llm:
            assert case.name not in scored_names

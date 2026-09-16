"""The eval suite. `uv run python -m evals.run`.

CLAUDE.md: "Any prompt or model change requires rerunning evals; regressions
block merge." This prints one line per eval and exits non-zero if any of
them failed — SKIPPED (the LLM gateway is unreachable; see llm_probe.py)
does not fail the run, since that says nothing about whether the code
under test regressed.
"""

from __future__ import annotations

import argparse
import sys

from app.config.settings import get_settings
from app.llm.client import LlmClient
from evals import (
    clustering,
    fact_checker_catch_rate,
    freshness,
    groundedness,
    neutrality,
    tag_accuracy,
)
from evals.llm_probe import llm_gateway_reachable
from evals.schemas import EvalResult, EvalStatus

UNREACHABLE_DETAIL = "the LLM gateway is unreachable — see docs/BACKLOG.md's blockers"


def _skip(name: str, threshold: float) -> EvalResult:
    return EvalResult(
        name=name, status=EvalStatus.SKIPPED, threshold=threshold, detail=UNREACHABLE_DETAIL
    )


def run_all() -> list[EvalResult]:
    settings = get_settings()
    results: list[EvalResult] = []

    # Deterministic tier: no LLM, always runs.
    results.append(freshness.run())
    results.append(fact_checker_catch_rate.run_deterministic_tier())
    results.append(clustering.run_title_baseline())
    results.append(neutrality.run())

    # LLM-dependent tier: skipped, not failed, when the gateway is down.
    if llm_gateway_reachable(settings):
        with LlmClient(settings=settings) as llm:
            results.append(fact_checker_catch_rate.run_full_pipeline(llm))
            results.append(groundedness.run(llm))
            results.append(tag_accuracy.run(llm))
            results.append(clustering.run_full_pipeline(llm))
    else:
        results.append(
            _skip(
                "fact_checker_catch_rate.full_pipeline",
                fact_checker_catch_rate.FULL_PIPELINE_THRESHOLD,
            )
        )
        results.append(_skip("groundedness", groundedness.THRESHOLD))
        results.append(_skip("tag_accuracy", tag_accuracy.THRESHOLD))
        results.append(_skip("clustering.full_pipeline", clustering.FULL_PIPELINE_THRESHOLD))

    return results


def _format_score(result: EvalResult) -> str:
    if result.score is None:
        return "-"
    return f"{result.score:.2f}" + (f" (>= {result.threshold:.2f})" if result.threshold else "")


def print_report(results: list[EvalResult], *, verbose: bool) -> None:
    name_width = max(len(r.name) for r in results) + 2
    for result in results:
        marker = {
            EvalStatus.PASSED: "PASS",
            EvalStatus.FAILED: "FAIL",
            EvalStatus.SKIPPED: "SKIP",
        }[result.status]
        header = f"{marker}  {result.name.ljust(name_width)} {_format_score(result):<18}"
        print(f"{header} {result.detail}")

        # A failed eval always names what broke; --verbose additionally
        # shows every case (including the ones that passed) for evals that
        # did run, so a case list can be sanity-checked against the fixture.
        cases_to_show = result.cases if verbose else result.failing_cases
        for case in cases_to_show:
            mark = "+" if case.passed else "-"
            print(f"       {mark} {case.name}: {case.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the eval suite.")
    parser.add_argument(
        "--verbose", action="store_true", help="print every case, not just a summary"
    )
    args = parser.parse_args(argv)

    results = run_all()
    print_report(results, verbose=args.verbose)

    failed = [r for r in results if r.status is EvalStatus.FAILED]
    skipped = [r for r in results if r.status is EvalStatus.SKIPPED]
    print()
    print(
        f"{len(results)} evals: {len(results) - len(failed) - len(skipped)} passed, "
        f"{len(failed)} failed, {len(skipped)} skipped"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

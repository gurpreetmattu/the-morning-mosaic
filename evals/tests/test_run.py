from __future__ import annotations

import pytest

from evals.run import main
from evals.schemas import CaseResult, EvalResult, EvalStatus


def test_exits_zero_when_nothing_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "evals.run.run_all",
        lambda: [
            EvalResult(name="a", status=EvalStatus.PASSED, score=1.0, threshold=1.0),
            EvalResult(name="b", status=EvalStatus.SKIPPED, threshold=0.9, detail="unreachable"),
        ],
    )
    assert main([]) == 0


def test_exits_non_zero_when_something_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "evals.run.run_all",
        lambda: [EvalResult(name="a", status=EvalStatus.FAILED, score=0.5, threshold=1.0)],
    )
    assert main([]) == 1


def test_a_skip_alone_does_not_fail_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "evals.run.run_all",
        lambda: [EvalResult(name="a", status=EvalStatus.SKIPPED, threshold=0.9)],
    )
    assert main([]) == 0


def test_failing_cases_are_printed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "evals.run.run_all",
        lambda: [
            EvalResult(
                name="a",
                status=EvalStatus.FAILED,
                score=0.5,
                threshold=1.0,
                cases=[
                    CaseResult(name="ok-case", passed=True),
                    CaseResult(name="bad-case", passed=False, detail="broke"),
                ],
            )
        ],
    )
    main([])
    output = capsys.readouterr().out
    assert "bad-case" in output
    assert "broke" in output
    assert "ok-case" not in output  # only failures print without --verbose


def test_verbose_lists_every_case_even_when_passed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "evals.run.run_all",
        lambda: [
            EvalResult(
                name="a",
                status=EvalStatus.PASSED,
                score=1.0,
                threshold=1.0,
                cases=[CaseResult(name="ok-case", passed=True)],
            )
        ],
    )
    main(["--verbose"])
    assert "ok-case" in capsys.readouterr().out


def test_without_verbose_a_passed_evals_cases_are_not_listed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "evals.run.run_all",
        lambda: [
            EvalResult(
                name="a",
                status=EvalStatus.PASSED,
                score=1.0,
                threshold=1.0,
                cases=[CaseResult(name="ok-case", passed=True)],
            )
        ],
    )
    main([])
    assert "ok-case" not in capsys.readouterr().out

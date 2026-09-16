from __future__ import annotations

from evals import neutrality
from evals.schemas import EvalStatus


def test_neutral_passages_have_no_loaded_terms() -> None:
    assert (
        neutrality.loaded_terms("The finance minister presented the annual budget on Tuesday.")
        == []
    )


def test_loaded_passages_are_caught() -> None:
    found = neutrality.loaded_terms("The minister's disastrous and shameful decision drew outrage.")
    assert "disastrous" in found
    assert "shameful" in found
    assert "outrage" in found


def test_the_heuristic_is_case_insensitive() -> None:
    assert "corrupt" in neutrality.loaded_terms("The CORRUPT official resigned.")


def test_the_fixture_set_passes_at_full_marks() -> None:
    result = neutrality.run()

    assert result.status is EvalStatus.PASSED
    assert result.score == 1.0

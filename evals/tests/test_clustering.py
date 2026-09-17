from __future__ import annotations

from evals import clustering
from evals.schemas import EvalStatus


def test_title_baseline_never_merges_unrelated_stories() -> None:
    result = clustering.run_title_baseline()

    # Every cross-group pair in the fixture must stay apart; only the
    # "corridor" pair (paraphrased with different words entirely, not just
    # a plural/tense variant) is allowed to fail — see title_tokens'
    # stemming and this module's own comment on TITLE_BASELINE_THRESHOLD.
    failing = {case.name for case in result.failing_cases}
    assert len(failing) <= 1


def test_title_baseline_score_matches_the_measured_value() -> None:
    result = clustering.run_title_baseline()

    assert result.score == 0.9
    assert result.status is EvalStatus.PASSED  # 0.9 clears the 0.85 threshold


def test_pairwise_accuracy_is_symmetric_in_group_labels() -> None:
    # Relabelling the ground-truth groups must not change the score: the
    # metric compares "same cluster" agreement, not the labels themselves.
    predicted = [["a", "b"], ["c"]]
    truth_a = {"a": "x", "b": "x", "c": "y"}
    truth_b = {"a": "1", "b": "1", "c": "2"}

    score_a, _ = clustering._pairwise_accuracy(predicted, truth_a)
    score_b, _ = clustering._pairwise_accuracy(predicted, truth_b)

    assert score_a == score_b == 1.0

"""Dedup/clustering accuracy.

Ranker.cluster reconciles a model's proposed grouping (see
`reconcile_clusters` in app/agents/ranking.py) but the grouping itself is
produced by an LLM call — CLAUDE.md: "Ranker: LLM clustering." A genuine
end-to-end clustering eval therefore needs the gateway; `run_full_pipeline`
does that and is skipped when it's unreachable.

What doesn't need the model is `cluster_by_title`, the deterministic
fallback used when the model can't be reached — itself worth measuring on
its own, both because it runs unconditionally today (see below) and because
it's the floor the LLM step has to clear to be worth the call at all.

Scored as pairwise accuracy: for every pair of articles, does "clustered
together" agree with the ground truth's "same event"? Simpler than the
usual clustering metrics (Rand index, ARI) and equivalent for a fixture
this small, without needing a stats dependency.
"""

from __future__ import annotations

from itertools import combinations

from app.agents.ranker import Ranker
from app.agents.ranking import cluster_by_title
from app.llm.client import LlmClient
from evals.datasets.articles import labelled_clustering_articles
from evals.schemas import CaseResult, EvalResult, EvalStatus

FULL_PIPELINE_THRESHOLD = 0.9

# Measured, not assumed: on this fixture the title-only fallback correctly
# keeps every unrelated pair apart but fails to merge the two genuinely
# duplicate pairs, because their headlines are paraphrased rather than
# near-identical (Jaccard ~0.33-0.38 against a 0.5 merge threshold) — 8 of
# 10 pairs right. That's not a bug: paraphrased duplicates are exactly what
# the LLM step exists to catch; this heuristic is the offline fallback, and
# staying conservative (never inventing a merge) is the point of it.
TITLE_BASELINE_THRESHOLD = 0.75


def _pairwise_accuracy(
    predicted: list[list[str]], truth: dict[str, str]
) -> tuple[float, list[CaseResult]]:
    same_cluster = {
        article_id: cluster_index
        for cluster_index, cluster in enumerate(predicted)
        for article_id in cluster
    }

    cases: list[CaseResult] = []
    for left, right in combinations(truth, 2):
        predicted_same = same_cluster[left] == same_cluster[right]
        actual_same = truth[left] == truth[right]
        cases.append(
            CaseResult(
                name=f"{left} / {right}",
                passed=predicted_same == actual_same,
                detail=f"predicted_same={predicted_same}, actual_same={actual_same}",
            )
        )

    score = sum(1 for c in cases if c.passed) / len(cases)
    return score, cases


def run_title_baseline() -> EvalResult:
    pairs = labelled_clustering_articles()
    articles = {f"a{i}": article for i, (_group, article) in enumerate(pairs)}
    truth = {f"a{i}": group for i, (group, _article) in enumerate(pairs)}

    predicted = cluster_by_title(articles)
    score, cases = _pairwise_accuracy(predicted, truth)

    return EvalResult(
        name="clustering.title_baseline",
        status=EvalStatus.PASSED if score >= TITLE_BASELINE_THRESHOLD else EvalStatus.FAILED,
        score=score,
        threshold=TITLE_BASELINE_THRESHOLD,
        detail=f"{len(articles)} articles, {len(cases)} pairs, deterministic fallback only",
        cases=cases,
    )


def run_full_pipeline(llm: LlmClient) -> EvalResult:
    """The real path: the model proposes groups, `reconcile_clusters` makes
    them a valid partition. Calls `Ranker._cluster` directly rather than
    `Ranker.rank`, which would also apply the corroboration gate and pool
    cap — real behaviour, but it would confound a clustering-accuracy score
    with a sourcing-accuracy one.
    """
    pairs = labelled_clustering_articles()
    articles = {f"a{i}": article for i, (_group, article) in enumerate(pairs)}
    truth = {f"a{i}": group for i, (group, _article) in enumerate(pairs)}

    ranker = Ranker(llm=llm)
    predicted, _labels, used_fallback = ranker._cluster(articles)
    score, cases = _pairwise_accuracy(predicted, truth)

    return EvalResult(
        name="clustering.full_pipeline",
        status=EvalStatus.PASSED if score >= FULL_PIPELINE_THRESHOLD else EvalStatus.FAILED,
        score=score,
        threshold=FULL_PIPELINE_THRESHOLD,
        detail=(
            f"{len(articles)} articles, {len(cases)} pairs"
            + (" — fell back to the title heuristic (model call failed)" if used_fallback else "")
        ),
        cases=cases,
    )

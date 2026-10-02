"""GenreDiagnostics must explain a thin section from facts the pipeline already has."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.agents.diagnostics import categorize_abandon, with_collection, with_pool
from app.agents.schemas import (
    GenreDiagnostics,
    PoolDropped,
    PoolDropReason,
    StoryPool,
)
from app.buildreport import format_genre_diagnostics
from app.sources.schemas import (
    CollectedArticle,
    CollectionResult,
    Dropped,
    DropReason,
    Passage,
)


def article(source: str, n: int) -> CollectedArticle:
    now = datetime(2026, 10, 2, 4, 0, tzinfo=UTC)
    return CollectedArticle(
        source_key=source,
        genre="india",
        url=f"https://{source}.example/{n}",
        title=f"Synthetic headline {n}",
        published_at=now,
        fetched_at=now,
        text="Synthetic body. " * 30,
        passages=[Passage(ordinal=1, text="Synthetic body. " * 30)],
        content_hash=f"hash-{source}-{n}",
    )


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (None, "no_reason"),
        ("- claim 1: verification unavailable: LlmHttpError", "checker_unavailable"),
        ("- unparseable: model returned prose", "writer:unparseable"),
        ("- copied_text: sentence 2 matches the source", "writer:copied_text"),
        ("- headline: the figure 12% is not in the passages", "writer:headline"),
        ("the number 40 does not appear in P2", "claims_unsupported"),
    ],
)
def test_an_abandoned_story_is_filed_under_the_real_cause(
    reason: str | None, expected: str
) -> None:
    assert categorize_abandon(reason) == expected


def test_checker_outage_wins_over_a_writer_looking_line() -> None:
    """An outage says nothing about the story, so it must never read as a content failure."""
    reason = "- headline: verification unavailable: LlmHttpError"
    assert categorize_abandon(reason) == "checker_unavailable"


def test_collection_counts_sources_and_drops() -> None:
    collected = CollectionResult(
        genre="india",
        articles=[article("the-hindu", 1), article("the-hindu", 2), article("scroll-in", 1)],
        dropped=[Dropped(url="https://x.example/1", source_key="x", reason=DropReason.TOO_OLD)],
    )

    result = with_collection(GenreDiagnostics(), collected)

    assert result.collected == 3
    assert result.articles_by_source == {"scroll-in": 1, "the-hindu": 2}
    assert result.collector_drops == {"too_old": 1}


def test_pool_records_fallback_clustering_and_drop_reasons() -> None:
    pool = StoryPool(
        genre="india",
        stories=[],
        dropped=[
            PoolDropped(
                event_label="a", source_keys=["x"], reason=PoolDropReason.INSUFFICIENT_CORROBORATION
            ),
            PoolDropped(
                event_label="b", source_keys=["y"], reason=PoolDropReason.INSUFFICIENT_CORROBORATION
            ),
        ],
        used_fallback_clustering=True,
    )

    result = with_pool(GenreDiagnostics(), pool)

    assert result.used_fallback_clustering is True
    assert result.clusters == 2
    assert result.pooled == 0
    assert result.pool_drops == {"insufficient_corroboration": 2}


def test_the_report_line_names_the_cause_in_plain_words() -> None:
    lines = format_genre_diagnostics(
        "india",
        GenreDiagnostics(
            collected=40,
            articles_by_source={"the-hindu": 7},
            clusters=31,
            used_fallback_clustering=True,
            pooled=3,
            pool_drops={"insufficient_corroboration": 28},
            attempted=3,
            write_cycles=9,
            abandoned={"checker_unavailable": 3},
        ).model_dump(mode="json"),
    )

    text = "\n".join(lines)
    assert "clustering: FALLBACK" in text
    assert "insufficient_corroboration 28" in text
    assert "checker_unavailable 3" in text
    assert "9 write cycles" in text

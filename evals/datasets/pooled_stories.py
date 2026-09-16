"""Synthetic pooled stories — Writer input — for the groundedness and tag
accuracy evals, which need the real model to produce something worth
scoring.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.agents.schemas import Corroboration, PooledStory
from app.config.schemas import GenreKey
from app.sources.schemas import CollectedArticle, Passage

NOW = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)


def _article(source_key: str, genre: GenreKey, title: str, text: str) -> CollectedArticle:
    return CollectedArticle(
        source_key=source_key,
        genre=genre,
        url=f"https://example.test/{source_key}-{title[:20]}",
        title=title,
        published_at=NOW,
        fetched_at=NOW,
        text=text,
        passages=[
            Passage(ordinal=i + 1, text=chunk) for i, chunk in enumerate(text.split(". ")) if chunk
        ],
        content_hash=f"hash-{source_key}-{title}",
    )


def pooled_stories() -> list[tuple[GenreKey, PooledStory]]:
    """A handful of two-source, well-corroborated stories across genres."""
    cases: list[tuple[GenreKey, PooledStory]] = []

    business_text = (
        "The Reserve Bank of India raised the repo rate by 25 basis points to "
        "6.50 percent on Tuesday. Governor Shaktikanta Das said the move was "
        "needed to keep inflation within the central bank's target band. "
        "The rate increase was the third this year."
    )
    cases.append(
        (
            "business",
            PooledStory(
                event_label="rbi-repo-rate",
                articles=[
                    _article("wire-service", "business", "RBI raises repo rate", business_text),
                    _article(
                        "daily-outlet",
                        "business",
                        "Central bank hikes rates again",
                        business_text,
                    ),
                ],
                corroboration=Corroboration.CORROBORATED,
                hedged=False,
                score=10.0,
                rank=1,
            ),
        )
    )

    india_text = (
        "The Ministry of Railways cleared a 350 kilometre high speed rail "
        "corridor between Mumbai and Ahmedabad on Monday. Minister Ashwini "
        "Vaishnaw said the project would be completed by 2029 and would cut "
        "travel time between the two cities to two hours."
    )
    cases.append(
        (
            "india",
            PooledStory(
                event_label="mumbai-ahmedabad-corridor",
                articles=[
                    _article(
                        "wire-service", "india", "Railways clears bullet train corridor", india_text
                    ),
                    _article(
                        "regional-paper", "india", "High speed rail project approved", india_text
                    ),
                ],
                corroboration=Corroboration.CORROBORATED,
                hedged=False,
                score=9.0,
                rank=1,
            ),
        )
    )

    return cases

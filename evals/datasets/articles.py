"""Synthetic collected articles, for the freshness and clustering evals."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.sources.schemas import CollectedArticle, Passage

BUILD_TIME = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)  # 04:00 IST


def make_article(
    *,
    source_key: str,
    genre: str,
    url: str,
    title: str,
    age: timedelta,
    text: str,
) -> CollectedArticle:
    published = BUILD_TIME - age
    return CollectedArticle(
        source_key=source_key,
        genre=genre,  # type: ignore[arg-type]
        url=url,
        title=title,
        published_at=published,
        fetched_at=BUILD_TIME,
        text=text,
        passages=[
            Passage(ordinal=i + 1, text=chunk) for i, chunk in enumerate(text.split(". ")) if chunk
        ],
        content_hash=f"hash-{url}",
    )


def fresh_and_stale_articles() -> list[CollectedArticle]:
    """A mix spanning the 24-hour freshness window, for the freshness eval."""
    return [
        make_article(
            source_key="wire-service",
            genre="india",
            url="https://example.test/a1",
            title="Cabinet approves freight corridor",
            age=timedelta(hours=1),
            text="The cabinet approved the eastern freight corridor on Tuesday.",
        ),
        make_article(
            source_key="wire-service",
            genre="business",
            url="https://example.test/a2",
            title="Markets close higher",
            age=timedelta(hours=6),
            text="The benchmark index closed two percent higher on Tuesday.",
        ),
        make_article(
            source_key="daily-outlet",
            genre="india",
            url="https://example.test/a3",
            title="State budget presented",
            age=timedelta(hours=18),
            text="The state government presented its annual budget on Monday.",
        ),
        make_article(
            source_key="daily-outlet",
            genre="technology",
            url="https://example.test/a4",
            title="Regulator opens consultation",
            age=timedelta(hours=23, minutes=45),
            text="The regulator opened a public consultation on data rules.",
        ),
    ]


# Two clusters (the same event covered by two outlets each) plus one
# singleton, for the title-based clustering eval. `group` is the eval's
# ground truth, never seen by the code under test.
_CLUSTERING_FIXTURES = [
    (
        "corridor",
        [
            ("wire-service", "Cabinet approves eastern freight corridor"),
            ("daily-outlet", "Government clears eastern freight corridor project"),
        ],
    ),
    (
        "budget",
        [
            ("wire-service", "State presents annual budget with tax relief"),
            ("regional-paper", "Annual state budget unveiled, taxes cut"),
        ],
    ),
    (
        "singleton",
        [
            ("daily-outlet", "Regulator opens consultation on data rules"),
        ],
    ),
]


def labelled_clustering_articles() -> list[tuple[str, CollectedArticle]]:
    """(ground_truth_group, article) pairs — same event, different outlets."""
    pairs: list[tuple[str, CollectedArticle]] = []
    for group, items in _CLUSTERING_FIXTURES:
        for index, (source_key, title) in enumerate(items):
            pairs.append(
                (
                    group,
                    make_article(
                        source_key=source_key,
                        genre="india",
                        url=f"https://example.test/{group}-{index}",
                        title=title,
                        age=timedelta(hours=2),
                        text=f"{title}. Officials confirmed the details on Tuesday.",
                    ),
                )
            )
    return pairs

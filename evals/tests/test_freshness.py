from __future__ import annotations

from evals import freshness
from evals.datasets.articles import BUILD_TIME, fresh_and_stale_articles
from evals.schemas import EvalStatus


def test_fixture_articles_are_all_within_the_hard_rule() -> None:
    """The fixture is deliberately a mix, but every article was collected —
    a real Collector run would already have dropped anything older."""
    result = freshness.run()

    assert result.status is EvalStatus.PASSED
    assert result.score == 1.0


def test_age_hours_matches_the_build_time_reference() -> None:
    articles = fresh_and_stale_articles()
    newest = min(articles, key=lambda a: freshness.age_hours(a))

    assert freshness.age_hours(newest) == (BUILD_TIME - newest.published_at).total_seconds() / 3600


def test_an_article_past_the_window_fails_its_case() -> None:
    from datetime import timedelta

    from evals.datasets.articles import make_article

    stale = make_article(
        source_key="daily-outlet",
        genre="india",
        url="https://example.test/stale",
        title="Old story",
        age=timedelta(hours=30),
        text="This ran long before the freshness window.",
    )
    case_passed = freshness.age_hours(stale) <= 24
    assert case_passed is False

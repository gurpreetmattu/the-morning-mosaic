"""Fixtures the LLM-dependent evals build on. Not exercised by anything
else when the gateway is unreachable, so this is what catches a fixture
that no longer builds without needing a live model to notice."""

from __future__ import annotations

from evals.datasets.articles import fresh_and_stale_articles, labelled_clustering_articles
from evals.datasets.pooled_stories import pooled_stories


def test_pooled_stories_have_at_least_two_independent_sources() -> None:
    for _genre, story in pooled_stories():
        assert len({article.source_key for article in story.articles}) >= 2


def test_pooled_stories_cover_more_than_one_genre() -> None:
    genres = {genre for genre, _story in pooled_stories()}
    assert len(genres) >= 2


def test_freshness_fixture_has_a_mix_of_ages() -> None:
    articles = fresh_and_stale_articles()
    assert len(articles) >= 3


def test_clustering_fixture_has_at_least_one_true_duplicate_pair() -> None:
    pairs = labelled_clustering_articles()
    groups = [group for group, _article in pairs]
    assert any(groups.count(group) > 1 for group in set(groups))

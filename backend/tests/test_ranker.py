"""Ranker: clustering is advisory, corroboration and scoring are not."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import respx

from app.agents.ranker import Ranker
from app.agents.ranking import (
    cluster_by_title,
    corroboration_for,
    independent_sources,
    meets_gate,
    reconcile_clusters,
    score_cluster,
    syndication_overlap,
    title_similarity,
)
from app.agents.schemas import Corroboration, PoolDropReason
from app.config.schemas import GenresConfig, SourcesConfig
from app.config.settings import Settings
from app.llm.client import LlmClient
from app.sources.schemas import CollectedArticle, CollectionResult, Passage

PRIMARY = "https://primary.llm"
NOW = datetime(2026, 9, 17, 4, 30, tzinfo=UTC)

# tier 1 = wire/official, 2 = established outlet, 3 = entertainment/gossip
TIERS = {"wire": 1, "daily": 2, "herald": 2, "chronicle": 2, "gossip": 3, "tattle": 3}


def article(source: str, title: str, *, hours_old: float = 2.0, body: str = "") -> CollectedArticle:
    # Alternating source/title tokens rather than shared boilerplate: two
    # articles from different (source, title) pairs must never look like
    # syndicated copies of each other just because this fixture padded them
    # out to passage length the same way.
    filler = " ".join([source, title] * 6)
    text = body or f"{title}. {filler} provides supporting detail for this report."
    return CollectedArticle(
        source_key=source,
        genre="india",
        url=f"https://{source}.example/{abs(hash(title)) % 10**8}",
        title=title,
        published_at=NOW - timedelta(hours=hours_old),
        fetched_at=NOW,
        text=text,
        passages=[Passage(ordinal=1, text=text)],
        content_hash=f"h{abs(hash(source + title)) % 10**12}",
    )


def sources_config() -> SourcesConfig:
    return SourcesConfig.model_validate(
        {
            "sources": [
                {
                    "key": key,
                    "name": key.title(),
                    "homepage": f"https://{key}.example/",
                    "tier": tier,
                    "terms_url": f"https://{key}.example/terms",
                    "terms_confirmed": True,
                    "robots_checked": True,
                    "enabled": True,
                    "feeds": [{"url": f"https://{key}.example/feed", "genres": ["india"]}],
                }
                for key, tier in TIERS.items()
            ]
        }
    )


def settings() -> Settings:
    return Settings.model_validate(
        {
            "base_url": "https://example.com",
            "database_url": "postgresql://u:p@localhost/db",
            "smtp_host": "smtp.example.com",
            "sender_email": "news@example.com",
            "sender_name": "Example",
            "gmail_app_password": "x",
            "imap_host": "imap.example.com",
            "admin_email": "admin@example.com",
            "freellmpool_url": PRIMARY,
            "freellmpool_api_key": "x",
            "token_signing_key": "x",
        }
    )


def models_config() -> Any:
    from app.config.schemas import ModelsConfig

    spec = {"model": "rank-1", "temperature": 0.0, "max_output_tokens": 512, "pinned": False}
    return ModelsConfig.model_validate(
        {
            "request_timeout_seconds": 5.0,
            "max_attempts": 1,
            "agents": {
                "orchestrator": spec,
                "ranker": spec,
                "writer": {**spec, "pinned": True},
                "fact_checker": {**spec, "pinned": True},
                "image_finder": spec,
            },
        }
    )


def ranker(genre_corroboration: str = "strict") -> Ranker:
    genres = load_genres_with(genre_corroboration)
    client = LlmClient(settings=settings(), models=models_config(), sleep=lambda _: None)
    return Ranker(llm=client, genres=genres, sources=sources_config())


def load_genres_with(corroboration: str) -> GenresConfig:
    from app.config.loader import load_genres

    real = load_genres()
    payload = real.model_dump()
    for genre in payload["genres"]:
        if genre["key"] == "india":
            genre["corroboration"] = corroboration
    return GenresConfig.model_validate(payload)


def llm_clusters(groups: list[dict[str, Any]]) -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "c",
                "object": "chat.completion",
                "created": 0,
                "model": "rank-1",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"clusters": groups}),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
    )


def collected(*articles: CollectedArticle) -> CollectionResult:
    return CollectionResult(genre="india", articles=list(articles))


# ------------------------------------------------------- corroboration gate


def test_two_independent_outlets_corroborate() -> None:
    cluster = [article("daily", "Rail corridor cleared"), article("herald", "Corridor approved")]
    assert corroboration_for(cluster, TIERS) == Corroboration.CORROBORATED


def test_a_single_wire_source_is_enough_on_its_own() -> None:
    """Tier 1 is a wire service or official body: primary by definition."""
    assert corroboration_for([article("wire", "Official statement")], TIERS) == (
        Corroboration.PRIMARY_OFFICIAL
    )


def test_one_outlet_alone_is_single_source() -> None:
    assert corroboration_for([article("daily", "Exclusive")], TIERS) == Corroboration.SINGLE_SOURCE


def test_gossip_only_coverage_is_tier3() -> None:
    cluster = [article("gossip", "Rumour"), article("tattle", "Rumour too")]
    assert corroboration_for(cluster, TIERS) == Corroboration.TIER3_ONLY


def test_syndicated_wire_copy_counts_as_one_voice_not_two() -> None:
    """Two outlets running the same wire report, lightly rewritten, are not
    independent — identical text is already caught by the Collector's
    content hash before this ever runs, so this has to be near-identical
    rather than byte-identical to exercise the check at all."""
    body = (
        "The union cabinet approved a new eastern freight rail corridor on "
        "Tuesday, clearing the way for construction to begin in the next "
        "financial year, officials briefed on the decision said."
    )
    original = article("wire", "Cabinet clears freight corridor", body=body)
    # A second outlet's rewrite: one clause reordered, everything else verbatim.
    rewrite = article(
        "daily",
        "Corridor plan cleared by cabinet",
        body=(
            "Officials briefed on the decision said the union cabinet approved "
            "a new eastern freight rail corridor on Tuesday, clearing the way "
            "for construction to begin in the next financial year."
        ),
    )

    assert syndication_overlap(original, rewrite) >= 0.5
    assert independent_sources([original, rewrite], TIERS) == 1
    assert corroboration_for([original, rewrite], TIERS) == Corroboration.PRIMARY_OFFICIAL


def test_independently_written_coverage_of_the_same_event_is_not_syndication() -> None:
    """Two outlets covering the same event in their own words share topical
    vocabulary, which must not be mistaken for one being a copy of the
    other."""
    daily = article(
        "daily",
        "Corridor cleared",
        body=(
            "The union cabinet gave its approval on Tuesday to a long-delayed "
            "freight corridor project connecting the eastern coalfields to the "
            "port network, a step planners have sought for over a decade."
        ),
    )
    herald = article(
        "herald",
        "Freight line gets go-ahead",
        body=(
            "Ministers signed off on plans for a rail link intended to move "
            "coal more cheaply toward the coast, ending years of delay that "
            "industry groups had blamed on land acquisition disputes."
        ),
    )

    assert syndication_overlap(daily, herald) < 0.5
    assert independent_sources([daily, herald], TIERS) == 2
    assert corroboration_for([daily, herald], TIERS) == Corroboration.CORROBORATED


def test_strict_genres_reject_single_source_and_gossip() -> None:
    assert not meets_gate(Corroboration.SINGLE_SOURCE, strict=True)
    assert not meets_gate(Corroboration.TIER3_ONLY, strict=True)
    assert meets_gate(Corroboration.CORROBORATED, strict=True)
    assert meets_gate(Corroboration.PRIMARY_OFFICIAL, strict=True)


def test_standard_genres_accept_anything() -> None:
    assert all(meets_gate(level, strict=False) for level in Corroboration)


@respx.mock
def test_an_under_sourced_story_is_dropped_from_a_strict_genre() -> None:
    llm_clusters([{"event": "solo", "article_ids": ["a1"]}])
    pool = ranker("strict").rank(collected(article("daily", "Only we have this")), now=NOW)

    assert pool.stories == []
    assert pool.dropped[0].reason == PoolDropReason.INSUFFICIENT_CORROBORATION


@respx.mock
def test_the_same_story_survives_in_a_standard_genre_but_is_not_hedged() -> None:
    llm_clusters([{"event": "solo", "article_ids": ["a1"]}])
    pool = ranker("standard").rank(collected(article("daily", "Only we have this")), now=NOW)

    assert len(pool.stories) == 1
    assert pool.stories[0].hedged is False


@respx.mock
def test_a_tier3_only_story_is_marked_hedged() -> None:
    llm_clusters([{"event": "rumour", "article_ids": ["a1"]}])
    pool = ranker("standard").rank(collected(article("gossip", "Reportedly")), now=NOW)

    assert pool.stories[0].corroboration == Corroboration.TIER3_ONLY
    assert pool.stories[0].hedged is True


# ---------------------------------------------------- asking for more coverage


class FakeCollector:
    def __init__(self, *, second_pass: CollectionResult | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._second_pass = second_pass

    def collect(
        self, genre: Any, *, now: datetime | None = None, max_articles: int | None = None
    ) -> CollectionResult:
        self.calls.append({"genre": genre, "now": now, "max_articles": max_articles})
        return self._second_pass or CollectionResult(genre=genre, articles=[])


def two_cluster_replies(first: list[dict[str, Any]], second: list[dict[str, Any]]) -> None:
    def reply(groups: list[dict[str, Any]]) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "c",
                "object": "chat.completion",
                "created": 0,
                "model": "rank-1",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"clusters": groups}),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    respx.post(f"{PRIMARY}/chat/completions").mock(side_effect=[reply(first), reply(second)])


@respx.mock
def test_a_thinly_sourced_strict_story_asks_for_more_coverage() -> None:
    # Two articles so clustering actually calls the model rather than taking
    # the single-article shortcut in _cluster() — both from "daily", so still
    # only one independent source.
    first_report = article("daily", "Corridor cleared, initial report")
    second_report = article("daily", "More on the corridor plan")
    rescuing_article = article("herald", "Corridor approved")
    two_cluster_replies(
        first=[{"event": "corridor", "article_ids": ["a1", "a2"]}],
        second=[{"event": "corridor", "article_ids": ["a1", "a2", "a3"]}],
    )
    widened = CollectionResult(
        genre="india", articles=[first_report, second_report, rescuing_article]
    )
    collector = FakeCollector(second_pass=widened)

    pool = Ranker(
        llm=LlmClient(settings=settings(), models=models_config(), sleep=lambda _: None),
        genres=load_genres_with("strict"),
        sources=sources_config(),
        collector=collector,
    ).rank(collected(first_report, second_report), now=NOW)

    assert len(collector.calls) == 1
    assert collector.calls[0]["max_articles"] == 80
    assert len(pool.stories) == 1
    assert pool.stories[0].source_keys == ["daily", "herald"]
    assert pool.requested_more_coverage is True


@respx.mock
def test_no_collector_means_no_retry() -> None:
    llm_clusters([{"event": "solo", "article_ids": ["a1"]}])
    pool = ranker("strict").rank(collected(article("daily", "Only we have this")), now=NOW)

    assert pool.stories == []
    assert pool.requested_more_coverage is False


@respx.mock
def test_a_standard_genre_never_asks_for_more_coverage() -> None:
    llm_clusters([{"event": "solo", "article_ids": ["a1"]}])
    collector = FakeCollector()

    Ranker(
        llm=LlmClient(settings=settings(), models=models_config(), sleep=lambda _: None),
        genres=load_genres_with("standard"),
        sources=sources_config(),
        collector=collector,
    ).rank(collected(article("daily", "Only we have this")), now=NOW)

    assert collector.calls == []


@respx.mock
def test_no_new_coverage_leaves_the_original_pool_unchanged() -> None:
    llm_clusters([{"event": "solo", "article_ids": ["a1"]}])
    solo = article("daily", "Only we have this")
    # The Collector found the same single article again; nothing to rescue it with.
    collector = FakeCollector(second_pass=CollectionResult(genre="india", articles=[solo]))

    pool = Ranker(
        llm=LlmClient(settings=settings(), models=models_config(), sleep=lambda _: None),
        genres=load_genres_with("strict"),
        sources=sources_config(),
        collector=collector,
    ).rank(collected(solo), now=NOW)

    assert len(collector.calls) == 1
    assert pool.stories == []
    assert pool.requested_more_coverage is False


# -------------------------------------------------------------- neutrality


def test_scoring_ignores_everything_except_sources_tier_and_recency() -> None:
    """Two clusters identical in sourcing and age must score identically,
    however differently their headlines read."""
    left = [
        article("daily", "Government hails the new policy"),
        article("herald", "Policy praised"),
    ]
    right = [
        article("daily", "Opposition condemns the new policy"),
        article("herald", "Policy attacked"),
    ]
    assert score_cluster(left, TIERS, now=NOW) == score_cluster(right, TIERS, now=NOW)


def test_broader_coverage_outranks_narrower() -> None:
    broad = [article("daily", "x"), article("herald", "x"), article("chronicle", "x")]
    narrow = [article("daily", "y")]
    assert score_cluster(broad, TIERS, now=NOW) > score_cluster(narrow, TIERS, now=NOW)


def test_a_primary_source_outranks_an_outlet_of_equal_breadth() -> None:
    official = [article("wire", "x")]
    outlet = [article("daily", "x")]
    assert score_cluster(official, TIERS, now=NOW) > score_cluster(outlet, TIERS, now=NOW)


def test_fresher_outranks_older_when_sourcing_matches() -> None:
    fresh = [article("daily", "x", hours_old=1)]
    old = [article("daily", "y", hours_old=20)]
    assert score_cluster(fresh, TIERS, now=NOW) > score_cluster(old, TIERS, now=NOW)


# ---------------------------------------------- the model cannot be trusted


def test_invented_article_ids_are_discarded() -> None:
    articles = {"a1": article("daily", "one"), "a2": article("herald", "two")}
    groups = reconcile_clusters([["a1", "a99"], ["a2"]], articles)
    assert groups == [["a1"], ["a2"]]


def test_an_article_assigned_twice_keeps_its_first_placement() -> None:
    articles = {"a1": article("daily", "one"), "a2": article("herald", "two")}
    assert reconcile_clusters([["a1", "a2"], ["a2"]], articles) == [["a1", "a2"]]


def test_an_article_the_model_forgot_becomes_its_own_cluster() -> None:
    articles = {
        "a1": article("daily", "one"),
        "a2": article("herald", "two"),
        "a3": article("wire", "three"),
    }
    assert reconcile_clusters([["a1"]], articles) == [["a1"], ["a2"], ["a3"]]


@respx.mock
def test_clustering_falls_back_to_headline_overlap_when_the_model_fails() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(return_value=httpx.Response(500))
    pool = ranker("standard").rank(
        collected(article("daily", "Cabinet clears rail corridor plan"), article("gossip", "x")),
        now=NOW,
    )

    assert pool.used_fallback_clustering is True
    assert len(pool.stories) == 2


@respx.mock
def test_unparseable_model_output_falls_back_rather_than_failing() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"index": 0, "message": {"role": "a", "content": "not json"}}],
                "usage": {},
            },
        )
    )
    pool = ranker("standard").rank(
        collected(article("daily", "a"), article("herald", "b")), now=NOW
    )
    assert pool.used_fallback_clustering is True


# ------------------------------------------------------- clustering effects


@respx.mock
def test_clustering_two_outlets_together_turns_them_into_one_story() -> None:
    llm_clusters([{"event": "rail corridor", "article_ids": ["a1", "a2"]}])
    pool = ranker("strict").rank(
        collected(article("daily", "Corridor cleared"), article("herald", "Corridor approved")),
        now=NOW,
    )

    assert len(pool.stories) == 1
    assert pool.stories[0].source_keys == ["daily", "herald"]
    assert pool.stories[0].corroboration == Corroboration.CORROBORATED
    assert pool.stories[0].rank == 1


@respx.mock
def test_the_pool_is_capped_and_the_overflow_is_recorded() -> None:
    articles = [article("wire", f"Story number {index}") for index in range(12)]
    llm_clusters([{"event": f"e{i}", "article_ids": [f"a{i + 1}"]} for i in range(12)])

    pool = ranker("strict").rank(collected(*articles), now=NOW)
    assert len(pool.stories) == 10  # genres.yaml pool_size
    assert [s.rank for s in pool.stories] == list(range(1, 11))
    assert sum(d.reason == PoolDropReason.BELOW_POOL_CAP for d in pool.dropped) == 2


def test_an_empty_collection_yields_an_empty_pool() -> None:
    assert ranker().rank(CollectionResult(genre="india"), now=NOW).stories == []


# ------------------------------------------------- fallback clustering units


def test_headline_overlap_groups_the_same_event() -> None:
    articles = {
        "a1": article("daily", "Cabinet clears eastern rail corridor"),
        "a2": article("herald", "Cabinet clears rail corridor for east"),
        "a3": article("wire", "Monsoon floods displace thousands"),
    }
    groups = cluster_by_title(articles)
    assert sorted(len(g) for g in groups) == [1, 2]


def test_similarity_ignores_stopwords() -> None:
    assert title_similarity("The cabinet has cleared it", "Cabinet cleared") > 0.5

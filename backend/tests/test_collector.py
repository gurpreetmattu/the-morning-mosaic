"""The Collector's rules: whitelist, freshness, robots, and extraction.

All HTTP is intercepted; fixtures are synthetic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.agents.collector import Collector
from app.clock import edition_date_for, require_aware
from app.config.schemas import SourcesConfig
from app.sources.extract import extract_article, split_passages
from app.sources.fetch import Fetcher
from app.sources.freshness import freshness_verdict
from app.sources.robots import RobotsPolicy
from app.sources.schemas import DropReason

FIXTURES = Path(__file__).parent / "fixtures"
HOST = "https://news.example"
NOW = datetime(2026, 9, 16, 4, 30, tzinfo=UTC)

ARTICLE_HTML = (FIXTURES / "sample_article.html").read_text(encoding="utf-8")
TEASER_HTML = "<html><body><article><p>Subscribe to read this story.</p></article></body></html>"


def feed_xml(*, fresh: datetime | None = None, stale: datetime | None = None) -> str:
    raw = (FIXTURES / "sample_feed.xml").read_text(encoding="utf-8")
    return raw.replace(
        "{PUBDATE_FRESH}", format_datetime(fresh or NOW - timedelta(hours=3))
    ).replace("{PUBDATE_STALE}", format_datetime(stale or NOW - timedelta(days=9)))


def sources(*, enabled: bool = True, extra_feed: bool = False) -> SourcesConfig:
    feeds: list[dict[str, Any]] = [{"url": f"{HOST}/feed.xml", "genres": ["india"]}]
    if extra_feed:
        feeds.append({"url": f"{HOST}/feed2.xml", "genres": ["india"]})
    return SourcesConfig.model_validate(
        {
            "sources": [
                {
                    "key": "example-news",
                    "name": "Example News",
                    "homepage": f"{HOST}/",
                    "tier": 2,
                    "terms_url": f"{HOST}/terms",
                    "terms_confirmed": enabled,
                    "robots_checked": enabled,
                    "enabled": enabled,
                    "feeds": feeds,
                }
            ]
        }
    )


def collector(config: SourcesConfig | None = None) -> Collector:
    fetcher = Fetcher(user_agent="TheMorningMosaic/0.1 (+test)", sleep=lambda _: None)
    return Collector(
        fetcher=fetcher,
        robots=RobotsPolicy(fetcher, "TheMorningMosaic/0.1 (+test)"),
        sources=config or sources(),
    )


def mock_site(*, robots: str = "User-agent: *\nAllow: /") -> None:
    respx.get(f"{HOST}/robots.txt").mock(return_value=httpx.Response(200, text=robots))
    respx.get(f"{HOST}/feed.xml").mock(return_value=httpx.Response(200, text=feed_xml()))
    respx.get(f"{HOST}/a/rail-corridor").mock(return_value=httpx.Response(200, text=ARTICLE_HTML))


# --------------------------------------------------------------- happy path


@respx.mock
def test_a_fresh_article_is_collected_with_numbered_passages() -> None:
    mock_site()
    result = collector().collect("india", now=NOW)

    assert len(result.articles) == 1
    article = result.articles[0]
    assert article.url == f"{HOST}/a/rail-corridor"
    assert article.source_key == "example-news"
    # trafilatura normalises bylines (it strips the "A." initial's period).
    assert article.author is not None
    assert "Fictional Correspondent" in article.author
    assert article.passages[0].ordinal == 1
    assert article.passages[0].citation_id == "p1"
    assert len(article.passages) >= 3
    assert article.content_hash


@respx.mock
def test_short_fragments_do_not_become_citable_passages() -> None:
    mock_site()
    article = collector().collect("india", now=NOW).articles[0]
    assert all("Short aside" not in passage.text for passage in article.passages)


# ---------------------------------------------------------------- freshness


@respx.mock
def test_an_item_without_a_timestamp_is_dropped() -> None:
    mock_site()
    result = collector().collect("india", now=NOW)

    reasons = {drop.url: drop.reason for drop in result.dropped}
    assert reasons[f"{HOST}/a/undated"] == DropReason.NO_TIMESTAMP


@respx.mock
def test_an_item_older_than_the_window_is_dropped() -> None:
    mock_site()
    result = collector().collect("india", now=NOW)

    reasons = {drop.url: drop.reason for drop in result.dropped}
    assert reasons[f"{HOST}/a/port-upgrade"] == DropReason.TOO_OLD


@respx.mock
def test_a_stale_item_is_never_fetched() -> None:
    """Dropping after the fetch would still have hit the publisher."""
    mock_site()
    collector().collect("india", now=NOW)

    fetched = {call.request.url.path for call in respx.calls}
    assert "/a/port-upgrade" not in fetched
    assert "/a/undated" not in fetched


def test_a_future_dated_item_is_dropped() -> None:
    verdict = freshness_verdict(NOW + timedelta(hours=6), now=NOW)
    assert verdict == DropReason.FUTURE_DATED


def test_small_clock_skew_is_tolerated() -> None:
    assert freshness_verdict(NOW + timedelta(minutes=30), now=NOW) is None


def test_a_naive_timestamp_is_refused_rather_than_assumed() -> None:
    with pytest.raises(ValueError, match="naive datetime"):
        freshness_verdict(datetime(2026, 9, 16, 4, 0), now=NOW)


# ------------------------------------------------------------------- robots


@respx.mock
def test_a_disallowed_article_is_not_fetched() -> None:
    mock_site(robots="User-agent: *\nDisallow: /a/")
    result = collector().collect("india", now=NOW)

    assert result.articles == []
    assert result.dropped[0].reason == DropReason.ROBOTS_DISALLOWED
    assert "/a/rail-corridor" not in {call.request.url.path for call in respx.calls}


@respx.mock
def test_unreadable_robots_denies_rather_than_assumes_permission() -> None:
    """A 5xx means the rules are unknown, so nothing may be crawled."""
    respx.get(f"{HOST}/robots.txt").mock(return_value=httpx.Response(500))
    respx.get(f"{HOST}/feed.xml").mock(return_value=httpx.Response(200, text=feed_xml()))
    respx.get(f"{HOST}/a/rail-corridor").mock(return_value=httpx.Response(200, text=ARTICLE_HTML))

    result = collector().collect("india", now=NOW)
    assert result.articles == []
    assert result.dropped[0].reason == DropReason.ROBOTS_DISALLOWED


@respx.mock
def test_a_missing_robots_file_allows_crawling() -> None:
    mock_site()
    respx.get(f"{HOST}/robots.txt").mock(return_value=httpx.Response(404))

    assert len(collector().collect("india", now=NOW).articles) == 1


# ---------------------------------------------------------------- whitelist


@respx.mock
def test_a_disabled_source_is_never_contacted() -> None:
    mock_site()
    result = collector(sources(enabled=False)).collect("india", now=NOW)

    assert result.articles == []
    assert len(respx.calls) == 0, "a source without confirmed terms must not be fetched"


# -------------------------------------------------- extraction and failures


@respx.mock
def test_a_paywall_teaser_is_dropped_for_being_too_short() -> None:
    mock_site()
    respx.get(f"{HOST}/a/rail-corridor").mock(return_value=httpx.Response(200, text=TEASER_HTML))

    result = collector().collect("india", now=NOW)
    assert result.articles == []
    assert result.dropped[0].reason == DropReason.TOO_SHORT


@respx.mock
def test_the_same_story_syndicated_twice_is_collected_once() -> None:
    respx.get(f"{HOST}/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    respx.get(f"{HOST}/feed.xml").mock(return_value=httpx.Response(200, text=feed_xml()))
    # A second feed carrying the same story under a different URL.
    second = feed_xml().replace("/a/rail-corridor", "/syndicated/rail-corridor")
    respx.get(f"{HOST}/feed2.xml").mock(return_value=httpx.Response(200, text=second))
    respx.get(f"{HOST}/a/rail-corridor").mock(return_value=httpx.Response(200, text=ARTICLE_HTML))
    respx.get(f"{HOST}/syndicated/rail-corridor").mock(
        return_value=httpx.Response(200, text=ARTICLE_HTML)
    )

    result = collector(sources(extra_feed=True)).collect("india", now=NOW)
    assert len(result.articles) == 1
    assert DropReason.DUPLICATE_CONTENT in {drop.reason for drop in result.dropped}


@respx.mock
def test_a_dead_feed_is_recorded_without_losing_the_genre() -> None:
    mock_site()
    respx.get(f"{HOST}/feed2.xml").mock(return_value=httpx.Response(500))

    result = collector(sources(extra_feed=True)).collect("india", now=NOW)
    assert len(result.articles) == 1
    assert DropReason.FEED_FAILED in {drop.reason for drop in result.dropped}


@respx.mock
def test_an_article_that_fails_to_fetch_is_recorded() -> None:
    mock_site()
    respx.get(f"{HOST}/a/rail-corridor").mock(return_value=httpx.Response(404))

    result = collector().collect("india", now=NOW)
    assert result.articles == []
    assert result.dropped[0].reason == DropReason.FETCH_FAILED


@respx.mock
def test_drop_reasons_are_counted_for_monitoring() -> None:
    mock_site()
    counts = collector().collect("india", now=NOW).reason_counts()
    assert counts[DropReason.NO_TIMESTAMP] == 1
    assert counts[DropReason.TOO_OLD] == 1


# ------------------------------------------------------------ units, no HTTP


def test_passages_are_numbered_from_one_and_skip_short_lines() -> None:
    text = "A heading\n\n" + ("A sentence long enough to be worth citing in a summary. " * 2)
    passages = split_passages(text)
    assert [p.ordinal for p in passages] == [1]
    assert "A heading" not in passages[0].text


def test_extraction_returns_none_for_a_stub_page() -> None:
    assert extract_article("<html><body><p>Hi</p></body></html>") is None


def test_edition_date_follows_ist_not_utc() -> None:
    """20:00 UTC is already the next calendar day in India."""
    assert edition_date_for(datetime(2026, 9, 15, 20, 0, tzinfo=UTC)).isoformat() == "2026-09-16"


def test_require_aware_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="naive datetime"):
        require_aware(datetime(2026, 9, 16, 4, 0))

"""RSS parsing, and the fallback-timezone exception to "never guess a
naive timestamp."

feedparser normally handles RFC 822 dates fine; the exception this module
adds is narrow and only for a pubDate that is otherwise well-formed but
missing its timezone offset entirely — RBI's real feed, not a
hypothetical (docs/BACKLOG.md's accounts-provisioned entry).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.sources.feeds import parse_feed

RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example</title>
    <item>
      <title>{title}</title>
      <link>{link}</link>
      {pubdate_tag}
    </item>
  </channel>
</rss>
"""


def feed(*, pubdate: str | None) -> str:
    tag = f"<pubDate>{pubdate}</pubDate>" if pubdate else ""
    return RSS_TEMPLATE.format(title="A story", link="https://example.test/a", pubdate_tag=tag)


def test_a_well_formed_pubdate_parses_without_any_fallback() -> None:
    items = parse_feed(
        feed(pubdate="Thu, 17 Sep 2026 19:00:00 +0530"),
        source_key="wire",
        genre="business",
    )
    assert items[0].published_at == datetime(2026, 9, 17, 13, 30, tzinfo=UTC)


def test_no_pubdate_at_all_is_still_undated() -> None:
    items = parse_feed(feed(pubdate=None), source_key="wire", genre="business")
    assert items[0].published_at is None


def test_a_missing_timezone_offset_is_undated_with_no_fallback_configured() -> None:
    """The exact defect found live on RBI's feed: a real date, no offset."""
    items = parse_feed(
        feed(pubdate="Thu, 17 Sep 2026 19:00:00"),
        source_key="rbi",
        genre="business",
    )
    assert items[0].published_at is None


def test_a_missing_timezone_offset_uses_the_configured_fallback() -> None:
    items = parse_feed(
        feed(pubdate="Thu, 17 Sep 2026 19:00:00"),
        source_key="rbi",
        genre="business",
        fallback_timezone="Asia/Kolkata",
    )
    # 19:00 IST (UTC+5:30) is 13:30 UTC the same day.
    assert items[0].published_at == datetime(2026, 9, 17, 13, 30, tzinfo=UTC)


def test_the_fallback_is_not_used_when_a_real_offset_is_already_present() -> None:
    """A well-formed date with its own offset must never be reinterpreted
    through a different source's configured timezone."""
    items = parse_feed(
        feed(pubdate="Thu, 17 Sep 2026 19:00:00 +0000"),
        source_key="rbi",
        genre="business",
        fallback_timezone="Asia/Kolkata",
    )
    assert items[0].published_at == datetime(2026, 9, 17, 19, 0, tzinfo=UTC)


def test_an_unparseable_date_stays_undated_even_with_a_fallback_configured() -> None:
    items = parse_feed(
        feed(pubdate="not a date at all"),
        source_key="rbi",
        genre="business",
        fallback_timezone="Asia/Kolkata",
    )
    assert items[0].published_at is None

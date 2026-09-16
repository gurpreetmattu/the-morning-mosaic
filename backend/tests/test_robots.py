"""RobotsPolicy: reading Crawl-delay out of robots.txt.

Allow/deny behaviour itself is exercised end to end in test_collector.py;
this covers the crawl-delay wiring into the Fetcher on its own.
"""

from __future__ import annotations

import httpx
import respx

from app.sources.fetch import Fetcher
from app.sources.robots import RobotsPolicy

HOST = "https://news.example"
USER_AGENT = "TheMorningMosaic/0.1 (+test)"


@respx.mock
def test_a_declared_crawl_delay_is_passed_to_the_fetcher() -> None:
    respx.get(f"{HOST}/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nCrawl-delay: 7\nAllow: /")
    )
    fetcher = Fetcher(user_agent=USER_AGENT, sleep=lambda _: None)
    policy = RobotsPolicy(fetcher, USER_AGENT)

    assert policy.allows(f"{HOST}/a/story")

    assert fetcher._host_delay["news.example"] == 7.0


@respx.mock
def test_no_crawl_delay_line_leaves_the_fetchers_default_untouched() -> None:
    respx.get(f"{HOST}/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    fetcher = Fetcher(user_agent=USER_AGENT, sleep=lambda _: None)
    policy = RobotsPolicy(fetcher, USER_AGENT)

    assert policy.allows(f"{HOST}/a/story")

    assert fetcher._host_delay == {}

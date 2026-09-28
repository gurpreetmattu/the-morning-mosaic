"""Fetcher: retry/backoff and per-host crawl throttling.

All HTTP is intercepted; nothing here talks to a real network or sleeps for
real time.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.sources.fetch import Fetcher, FetchError

URL = "https://news.example/a/story"
HOST = "news.example"


def fetcher(
    *,
    max_attempts: int = 3,
    min_host_interval: float = 1.0,
    sleeps: list[float] | None = None,
    clock: list[float] | None = None,
) -> Fetcher:
    sleeps = sleeps if sleeps is not None else []
    clock = clock if clock is not None else [0.0]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    def monotonic() -> float:
        return clock[0]

    return Fetcher(
        user_agent="TheMorningMosaic/0.1 (+test)",
        max_attempts=max_attempts,
        min_host_interval=min_host_interval,
        sleep=sleep,
        monotonic=monotonic,
    )


# ------------------------------------------------------------------ retries


@respx.mock
def test_a_transient_status_is_retried_and_then_succeeds() -> None:
    route = respx.get(URL)
    route.side_effect = [httpx.Response(503), httpx.Response(200, text="ok")]

    response = fetcher().get(URL)

    assert response.text == "ok"
    assert route.call_count == 2


@respx.mock
def test_retries_are_exhausted_as_a_fetch_error() -> None:
    respx.get(URL).mock(return_value=httpx.Response(503))

    with pytest.raises(FetchError):
        fetcher(max_attempts=2).get(URL)


@respx.mock
def test_a_non_retryable_status_fails_on_the_first_attempt() -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(404))

    with pytest.raises(FetchError) as excinfo:
        fetcher().get(URL)

    assert excinfo.value.status_code == 404
    assert route.call_count == 1


@respx.mock
def test_extra_headers_are_sent_alongside_the_default_user_agent() -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, text="ok"))

    fetcher().get(URL, headers={"Authorization": "Client-ID secret"})

    sent = route.calls.last.request.headers
    assert sent["Authorization"] == "Client-ID secret"
    assert sent["User-Agent"] == "TheMorningMosaic/0.1 (+test)"


@respx.mock
def test_a_transport_error_is_retried() -> None:
    route = respx.get(URL)
    route.side_effect = [httpx.ConnectError("refused"), httpx.Response(200, text="ok")]

    response = fetcher().get(URL)

    assert response.text == "ok"
    assert route.call_count == 2


# ---------------------------------------------------------------- throttling


@respx.mock
def test_back_to_back_requests_to_the_same_host_are_throttled() -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, text="ok"))
    sleeps: list[float] = []
    subject = fetcher(min_host_interval=1.0, sleeps=sleeps)

    subject.get(URL)
    subject.get(URL)

    assert sleeps == [1.0]


@respx.mock
def test_a_declared_crawl_delay_overrides_the_default_minimum() -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, text="ok"))
    sleeps: list[float] = []
    subject = fetcher(min_host_interval=1.0, sleeps=sleeps)

    subject.set_crawl_delay(HOST, 5.0)
    subject.get(URL)
    subject.get(URL)

    assert sleeps == [5.0]


@respx.mock
def test_a_crawl_delay_never_lowers_the_default_minimum() -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, text="ok"))
    sleeps: list[float] = []
    subject = fetcher(min_host_interval=2.0, sleeps=sleeps)

    subject.set_crawl_delay(HOST, 0.5)
    subject.get(URL)
    subject.get(URL)

    assert sleeps == [2.0]


@respx.mock
def test_a_different_host_is_not_throttled_by_another_hosts_requests() -> None:
    other_url = "https://other.example/a/story"
    respx.get(URL).mock(return_value=httpx.Response(200, text="ok"))
    respx.get(other_url).mock(return_value=httpx.Response(200, text="ok"))
    sleeps: list[float] = []
    subject = fetcher(min_host_interval=1.0, sleeps=sleeps)

    subject.get(URL)
    subject.get(other_url)

    assert sleeps == []

"""HTTP fetching for feeds and articles.

The user agent is honest and identifies the project. We do not present as a
browser: a source that blocks an identified crawler is telling us not to
fetch it, and working around that would contradict the rule about respecting
robots.txt and site terms. Such a source stays disabled until its terms
review resolves the question.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_ATTEMPTS = 3

# Floor on requests to a single host, so an enabled source with many feeds
# and articles is never hammered even without a declared Crawl-delay.
DEFAULT_MIN_HOST_INTERVAL_SECONDS = 1.0

# Transient; worth another attempt.
RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


class FetchError(Exception):
    """The resource could not be retrieved.

    `status_code` is set when the server answered; it is None when the failure
    was transport-level or the retries were exhausted. Callers depend on that
    distinction — see RobotsPolicy.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class _TransientError(Exception):
    """Internal marker so tenacity retries only what should be retried."""


def user_agent_for(base_url: str) -> str:
    return f"TheMorningMosaic/0.1 (+{base_url.rstrip('/')}; daily newsletter; contact via site)"


class Fetcher:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        min_host_interval: float = DEFAULT_MIN_HOST_INTERVAL_SECONDS,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._user_agent = user_agent
        self._max_attempts = max_attempts
        self._min_host_interval = min_host_interval
        self._sleep = sleep
        self._monotonic = monotonic
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=True)
        self._last_request_at: dict[str, float] = {}
        # A host's own declared Crawl-delay, when RobotsPolicy has read one;
        # never lower than min_host_interval.
        self._host_delay: dict[str, float] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def set_crawl_delay(self, host: str, seconds: float) -> None:
        """Record a host's declared robots.txt Crawl-delay, in seconds."""
        self._host_delay[host] = seconds

    def _throttle(self, host: str) -> None:
        delay = max(self._min_host_interval, self._host_delay.get(host, 0.0))
        if delay <= 0:
            return
        last = self._last_request_at.get(host)
        if last is not None:
            wait = delay - (self._monotonic() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_request_at[host] = self._monotonic()

    def get(self, url: str) -> httpx.Response:
        """Fetch a URL, retrying transient failures. Raises FetchError."""
        self._throttle(urlsplit(url).netloc)
        try:
            for attempt in Retrying(
                stop=stop_after_attempt(self._max_attempts),
                wait=wait_exponential(multiplier=0.5, max=8.0),
                retry=retry_if_exception_type(_TransientError),
                sleep=self._sleep,
                reraise=True,
            ):
                with attempt:
                    return self._once(url)
        except _TransientError as exc:
            raise FetchError(f"{url}: {exc}") from exc
        raise FetchError(f"{url}: exhausted retries")  # pragma: no cover

    def _once(self, url: str) -> httpx.Response:
        try:
            response = self._client.get(url, headers={"User-Agent": self._user_agent})
        except httpx.TransportError as exc:
            raise _TransientError(f"{type(exc).__name__}: {exc}") from exc

        if response.status_code in RETRYABLE_STATUS:
            raise _TransientError(f"HTTP {response.status_code}")
        if not response.is_success:
            raise FetchError(f"{url}: HTTP {response.status_code}", response.status_code)
        return response

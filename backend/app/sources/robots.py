"""robots.txt enforcement.

Checked before every article fetch, and cached per host for the run.

Failure handling follows the conservative reading of the standard:

- 4xx (usually 404, no robots.txt) means everything is allowed.
- 5xx or a network failure means we do NOT know the site's rules, so nothing
  is allowed. A publisher having a bad afternoon must not be crawled against
  rules we could not read.
"""

from __future__ import annotations

from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from app.sources.fetch import Fetcher, FetchError


class RobotsPolicy:
    def __init__(self, fetcher: Fetcher, user_agent: str) -> None:
        self._fetcher = fetcher
        self._user_agent = user_agent
        # None means "could not read the rules", which denies.
        self._cache: dict[str, RobotFileParser | None] = {}

    def allows(self, url: str) -> bool:
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            return False
        origin = f"{parts.scheme}://{parts.netloc}"

        if origin not in self._cache:
            self._cache[origin] = self._load(origin)

        parser = self._cache[origin]
        if parser is None:
            return False
        return parser.can_fetch(self._user_agent, url)

    def _load(self, origin: str) -> RobotFileParser | None:
        parser = RobotFileParser()
        try:
            response = self._fetcher.get(f"{origin}/robots.txt")
        except FetchError as exc:
            status = exc.status_code
            if status is not None and 400 <= status < 500:
                parser.parse([])  # no rules published: everything is allowed
                return parser
            return None  # rules unknown: deny

        parser.parse(response.text.splitlines())
        delay = parser.crawl_delay(self._user_agent)
        if delay is not None:
            self._fetcher.set_crawl_delay(urlsplit(origin).netloc, float(delay))
        return parser

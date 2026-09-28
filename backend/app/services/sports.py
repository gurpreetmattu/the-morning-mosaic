"""Sports scores and fixtures (genre extras) for the sports genre. No LLM:
two calls to Cricbuzz's Cricket API (via RapidAPI) per edition_date,
persisted once in `extras` (genre-scoped, like movie releases).

**Terms: a real, open compliance gap, not a resolved one.** RapidAPI's own
platform terms explicitly defer data-usage rights to each API's own
provider ("API Provider, not Rapid, is responsible for... the API
Content/Terms applicable to each API"), and Cricbuzz's own site is a
JS-rendered SPA that did not yield explicit, checkable terms the way ECB's
or Wikipedia's did. Built anyway, with the owner's explicit go-ahead, but
this is recorded in docs/BACKLOG.md as unresolved — revisit if Cricbuzz's
actual terms surface (e.g. from the RapidAPI dashboard's provider-specific
terms tab, visible only when logged in) and they turn out to restrict this.

Cricbuzz's `status` field is used verbatim for scores rather than
reconstructing a result sentence from raw runs/wickets — it is their own
pre-written result text, not something this project generates.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now_utc, to_ist
from app.models.content import Extra
from app.models.enums import ExtraKind
from app.sources.fetch import Fetcher, FetchError

logger = logging.getLogger(__name__)

CRICBUZZ_HOST = "cricbuzz-cricket.p.rapidapi.com"
CRICBUZZ_RECENT_API = f"https://{CRICBUZZ_HOST}/matches/v1/recent"
CRICBUZZ_UPCOMING_API = f"https://{CRICBUZZ_HOST}/matches/v1/upcoming"
SPORTS_SOURCE = "Cricbuzz (via RapidAPI)"
ITEMS_PER_KIND = 3
SPORTS_GENRE = "sports"


class SportsFetchError(Exception):
    """The scores or fixtures could not be fetched or did not parse."""


def _headers(api_key: str) -> dict[str, str]:
    return {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": CRICBUZZ_HOST,
        # This host's WAF (Akamai, fronting Cricbuzz's real backend) rejects
        # the project's usual `Fetcher` User-Agent — specifically the
        # "(+https://...)" contact-URL parenthetical, confirmed live by
        # testing with and without it. Overridden here only, not in
        # `Fetcher` itself: this is a narrow WAF quirk on one authenticated,
        # keyed API call, not the "identify honestly to a source that might
        # not want to be crawled" case `user_agent_for` exists for.
        "User-Agent": "TheMorningMosaic/0.1",
    }


def _iter_matches(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for type_match in payload.get("typeMatches", []):
        for series_match in type_match.get("seriesMatches", []):
            wrapper = series_match.get("seriesAdWrapper")
            if not wrapper:
                continue
            yield from wrapper.get("matches", [])


def _ist_label(epoch_ms: object) -> str:
    try:
        moment = datetime.fromtimestamp(int(str(epoch_ms)) / 1000, tz=UTC)
    except (TypeError, ValueError):
        return ""
    return to_ist(moment).strftime("%d %b, %H:%M IST")


def fetch_scores(fetcher: Fetcher, *, api_key: str) -> list[dict[str, str]]:
    try:
        response = fetcher.get(CRICBUZZ_RECENT_API, headers=_headers(api_key))
        payload = response.json()
    except (FetchError, TypeError, ValueError) as exc:
        raise SportsFetchError(f"scores: {exc}") from exc

    scores = []
    for match in _iter_matches(payload):
        info = match.get("matchInfo", {})
        if info.get("state") != "Complete":
            continue
        status = info.get("status")
        team1 = (info.get("team1") or {}).get("teamName")
        team2 = (info.get("team2") or {}).get("teamName")
        end_date = info.get("endDate")
        if not (status and team1 and team2 and end_date):
            continue
        scores.append(
            {
                "team1": str(team1),
                "team2": str(team2),
                "status": str(status),
                "end_date": str(end_date),
            }
        )
    scores.sort(key=lambda s: int(s["end_date"]), reverse=True)
    return [
        {"team1": s["team1"], "team2": s["team2"], "status": s["status"]}
        for s in scores[:ITEMS_PER_KIND]
    ]


def fetch_fixtures(fetcher: Fetcher, *, api_key: str) -> list[dict[str, str]]:
    try:
        response = fetcher.get(CRICBUZZ_UPCOMING_API, headers=_headers(api_key))
        payload = response.json()
    except (FetchError, TypeError, ValueError) as exc:
        raise SportsFetchError(f"fixtures: {exc}") from exc

    fixtures = []
    for match in _iter_matches(payload):
        info = match.get("matchInfo", {})
        if info.get("state") == "Complete":
            continue
        team1 = (info.get("team1") or {}).get("teamName")
        team2 = (info.get("team2") or {}).get("teamName")
        start_date = info.get("startDate")
        if not (team1 and team2 and start_date):
            continue
        fixtures.append({"team1": str(team1), "team2": str(team2), "start_date": str(start_date)})
    fixtures.sort(key=lambda f: int(f["start_date"]))
    return [
        {"team1": f["team1"], "team2": f["team2"], "when": _ist_label(f["start_date"])}
        for f in fixtures[:ITEMS_PER_KIND]
    ]


def _existing(session: Session, *, edition_date: date, kind: ExtraKind) -> Extra | None:
    return session.scalar(
        select(Extra).where(
            Extra.edition_date == edition_date,
            Extra.kind == kind,
            Extra.genre == SPORTS_GENRE,
        )
    )


def persist_sports_extras(
    session: Session,
    *,
    edition_date: date,
    fetcher: Fetcher,
    api_key: str | None,
    now: datetime | None = None,
) -> list[Extra]:
    """Fetch and store today's scores and fixtures, each once per
    edition_date. Never raises — a missing item is acceptable, same as
    every other extra.
    """
    if api_key is None:
        return []
    stamp = now or now_utc()
    persisted: list[Extra] = []

    if _existing(session, edition_date=edition_date, kind=ExtraKind.SCORE) is None:
        try:
            scores = fetch_scores(fetcher, api_key=api_key)
        except SportsFetchError:
            logger.warning("sports scores fetch failed", exc_info=True)
        else:
            if scores:
                row = Extra(
                    edition_date=edition_date,
                    kind=ExtraKind.SCORE,
                    genre=SPORTS_GENRE,
                    payload={"items": scores},
                    source_name=SPORTS_SOURCE,
                    source_url="https://www.cricbuzz.com/",
                    data_at=stamp,
                )
                session.add(row)
                persisted.append(row)

    if _existing(session, edition_date=edition_date, kind=ExtraKind.FIXTURE) is None:
        try:
            fixtures = fetch_fixtures(fetcher, api_key=api_key)
        except SportsFetchError:
            logger.warning("sports fixtures fetch failed", exc_info=True)
        else:
            if fixtures:
                row = Extra(
                    edition_date=edition_date,
                    kind=ExtraKind.FIXTURE,
                    genre=SPORTS_GENRE,
                    payload={"items": fixtures},
                    source_name=SPORTS_SOURCE,
                    source_url="https://www.cricbuzz.com/",
                    data_at=stamp,
                )
                session.add(row)
                persisted.append(row)

    session.flush()
    return persisted


def load_scores(session: Session, *, edition_date: date) -> list[dict[str, str]]:
    row = _existing(session, edition_date=edition_date, kind=ExtraKind.SCORE)
    return row.payload["items"] if row is not None else []


def load_fixtures(session: Session, *, edition_date: date) -> list[dict[str, str]]:
    row = _existing(session, edition_date=edition_date, kind=ExtraKind.FIXTURE)
    return row.payload["items"] if row is not None else []

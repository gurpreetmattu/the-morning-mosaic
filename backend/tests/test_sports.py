"""Sports scores and fixtures: two Cricbuzz (via RapidAPI) calls per
edition_date, cached; a failed or malformed fetch is omitted, never raised.
Genre-scoped, like movie releases.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import Extra
from app.models.enums import ExtraKind
from app.services.sports import (
    CRICBUZZ_RECENT_API,
    CRICBUZZ_UPCOMING_API,
    load_fixtures,
    load_scores,
    persist_sports_extras,
)
from app.sources.fetch import Fetcher

pytestmark = pytest.mark.integration

EDITION = date(2026, 9, 28)
NOW = datetime(2026, 9, 28, 1, 30, tzinfo=UTC)
RECENT_PATTERN = re.compile(rf"^{re.escape(CRICBUZZ_RECENT_API)}$")
UPCOMING_PATTERN = re.compile(rf"^{re.escape(CRICBUZZ_UPCOMING_API)}$")


def fetcher() -> Fetcher:
    """No real sleeping: a failing test would otherwise pay full backoff."""
    clock = [0.0]
    return Fetcher(
        user_agent="TheMorningMosaic/0.1 (+test)",
        sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        monotonic=lambda: clock[0],
    )


def _match(
    *,
    state: str,
    team1: str,
    team2: str,
    status: str | None = None,
    end_date: str | None = None,
    start_date: str | None = None,
) -> dict[str, object]:
    info: dict[str, object] = {
        "state": state,
        "team1": {"teamName": team1},
        "team2": {"teamName": team2},
    }
    if status is not None:
        info["status"] = status
    if end_date is not None:
        info["endDate"] = end_date
    if start_date is not None:
        info["startDate"] = start_date
    return {"matchInfo": info}


def _payload(*matches: dict[str, object]) -> dict[str, object]:
    return {
        "typeMatches": [
            {
                "matchType": "International",
                "seriesMatches": [{"seriesAdWrapper": {"seriesId": 1, "matches": list(matches)}}],
            }
        ]
    }


RECENT_PAYLOAD = _payload(
    _match(
        state="Complete",
        team1="India",
        team2="Pakistan",
        status="India won by 4 wickets",
        end_date="1000",
    ),
    _match(
        state="Complete",
        team1="Australia",
        team2="England",
        status="England won by 10 runs",
        end_date="2000",
    ),
    _match(state="In Progress", team1="Nepal", team2="Japan"),  # no status/end_date -> skipped
)

UPCOMING_PAYLOAD = _payload(
    _match(state="Upcoming", team1="Sri Lanka", team2="Nepal", start_date="3000"),
    _match(state="Upcoming", team1="India A", team2="Australia A", start_date="1000"),
    _match(state="Complete", team1="Old", team2="Match", status="done", end_date="1"),  # excluded
)


@respx.mock
def test_completed_matches_are_extracted_sorted_and_persisted(session: Session) -> None:
    respx.get(RECENT_PATTERN).mock(return_value=httpx.Response(200, json=RECENT_PAYLOAD))
    respx.get(UPCOMING_PATTERN).mock(return_value=httpx.Response(200, json={"typeMatches": []}))

    persisted = persist_sports_extras(
        session, edition_date=EDITION, fetcher=fetcher(), api_key="k", now=NOW
    )

    assert {row.kind for row in persisted} == {ExtraKind.SCORE}
    scores = load_scores(session, edition_date=EDITION)
    # Most recent (higher end_date) first; the in-progress match is excluded.
    assert scores == [
        {"team1": "Australia", "team2": "England", "status": "England won by 10 runs"},
        {"team1": "India", "team2": "Pakistan", "status": "India won by 4 wickets"},
    ]


@respx.mock
def test_upcoming_matches_are_extracted_sorted_and_persisted(session: Session) -> None:
    respx.get(RECENT_PATTERN).mock(return_value=httpx.Response(200, json={"typeMatches": []}))
    respx.get(UPCOMING_PATTERN).mock(return_value=httpx.Response(200, json=UPCOMING_PAYLOAD))

    persisted = persist_sports_extras(
        session, edition_date=EDITION, fetcher=fetcher(), api_key="k", now=NOW
    )

    assert {row.kind for row in persisted} == {ExtraKind.FIXTURE}
    fixtures = load_fixtures(session, edition_date=EDITION)
    # Soonest (lower start_date) first; the completed match is excluded.
    assert [f["team1"] for f in fixtures] == ["India A", "Sri Lanka"]


@respx.mock
def test_a_rerun_does_not_refetch(session: Session) -> None:
    recent_route = respx.get(RECENT_PATTERN).mock(
        return_value=httpx.Response(200, json=RECENT_PAYLOAD)
    )
    upcoming_route = respx.get(UPCOMING_PATTERN).mock(
        return_value=httpx.Response(200, json=UPCOMING_PAYLOAD)
    )

    persist_sports_extras(session, edition_date=EDITION, fetcher=fetcher(), api_key="k", now=NOW)
    second = persist_sports_extras(
        session, edition_date=EDITION, fetcher=fetcher(), api_key="k", now=NOW
    )

    assert second == []
    assert recent_route.call_count == 1
    assert upcoming_route.call_count == 1


def test_no_api_key_is_skipped_without_a_network_call(session: Session) -> None:
    persisted = persist_sports_extras(
        session, edition_date=EDITION, fetcher=fetcher(), api_key=None, now=NOW
    )

    assert persisted == []
    assert load_scores(session, edition_date=EDITION) == []


@respx.mock
def test_a_failed_fetch_is_omitted_instead_of_raising(session: Session) -> None:
    respx.get(RECENT_PATTERN).mock(return_value=httpx.Response(500))
    respx.get(UPCOMING_PATTERN).mock(return_value=httpx.Response(500))

    persisted = persist_sports_extras(
        session, edition_date=EDITION, fetcher=fetcher(), api_key="k", now=NOW
    )

    assert persisted == []
    rows = session.scalars(select(Extra).where(Extra.edition_date == EDITION)).all()
    assert rows == []


@respx.mock
def test_a_malformed_response_is_omitted_instead_of_raising(session: Session) -> None:
    respx.get(RECENT_PATTERN).mock(return_value=httpx.Response(200, json={"unexpected": True}))
    respx.get(UPCOMING_PATTERN).mock(return_value=httpx.Response(200, json={"unexpected": True}))

    persisted = persist_sports_extras(
        session, edition_date=EDITION, fetcher=fetcher(), api_key="k", now=NOW
    )

    assert persisted == []

"""Movie releases: one TMDB call per genre per edition_date, cached; a
failed or malformed fetch is omitted, never raised. Genre-scoped, unlike
weather/quotes/market — the first real use of `Extra.genre`.
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
from app.services.releases import (
    TMDB_UPCOMING_API,
    load_movie_releases,
    persist_movie_releases,
)
from app.sources.fetch import Fetcher

pytestmark = pytest.mark.integration

EDITION = date(2026, 9, 28)
NOW = datetime(2026, 9, 28, 1, 30, tzinfo=UTC)
URL_PATTERN = re.compile(rf"^{re.escape(TMDB_UPCOMING_API)}\?.*")

PAYLOAD = {
    "results": [
        {"title": "Later Movie", "release_date": "2026-10-16", "overview": "A later film."},
        {"title": "Sooner Movie", "release_date": "2026-10-02", "overview": "An earlier film."},
        {"title": "No Overview", "release_date": "2026-10-09"},
        {"title": "", "release_date": "2026-10-10"},
        {"title": "No Date"},
    ]
}


def fetcher() -> Fetcher:
    """No real sleeping: a failing test would otherwise pay full backoff."""
    clock = [0.0]
    return Fetcher(
        user_agent="TheMorningMosaic/0.1 (+test)",
        sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        monotonic=lambda: clock[0],
    )


@respx.mock
def test_a_fresh_fetch_is_sorted_capped_and_persisted(session: Session) -> None:
    respx.get(URL_PATTERN).mock(return_value=httpx.Response(200, json=PAYLOAD))

    row = persist_movie_releases(
        session, edition_date=EDITION, genre="bollywood", fetcher=fetcher(), api_key="k", now=NOW
    )

    assert row is not None
    assert row.kind == ExtraKind.MOVIE_RELEASE
    assert row.genre == "bollywood"
    assert row.source_name == "TMDB"

    releases = load_movie_releases(session, edition_date=EDITION, genre="bollywood")
    # Sorted by date, capped at 3, and entries missing a title or date dropped.
    assert [r["title"] for r in releases] == ["Sooner Movie", "No Overview", "Later Movie"]


@respx.mock
def test_a_rerun_does_not_refetch(session: Session) -> None:
    route = respx.get(URL_PATTERN).mock(return_value=httpx.Response(200, json=PAYLOAD))

    persist_movie_releases(
        session, edition_date=EDITION, genre="bollywood", fetcher=fetcher(), api_key="k", now=NOW
    )
    second = persist_movie_releases(
        session, edition_date=EDITION, genre="bollywood", fetcher=fetcher(), api_key="k", now=NOW
    )

    assert second is None
    assert route.call_count == 1


@respx.mock
def test_bollywood_and_hollywood_are_independent(session: Session) -> None:
    respx.get(URL_PATTERN).mock(return_value=httpx.Response(200, json=PAYLOAD))

    persist_movie_releases(
        session, edition_date=EDITION, genre="bollywood", fetcher=fetcher(), api_key="k", now=NOW
    )
    persist_movie_releases(
        session, edition_date=EDITION, genre="hollywood", fetcher=fetcher(), api_key="k", now=NOW
    )

    rows = session.scalars(select(Extra).where(Extra.edition_date == EDITION)).all()
    assert {row.genre for row in rows} == {"bollywood", "hollywood"}


def test_a_non_movie_genre_is_skipped_without_a_network_call(session: Session) -> None:
    row = persist_movie_releases(
        session, edition_date=EDITION, genre="india", fetcher=fetcher(), api_key="k", now=NOW
    )

    assert row is None
    assert load_movie_releases(session, edition_date=EDITION, genre="india") == []


def test_no_api_key_is_skipped(session: Session) -> None:
    row = persist_movie_releases(
        session, edition_date=EDITION, genre="bollywood", fetcher=fetcher(), api_key=None, now=NOW
    )

    assert row is None


@respx.mock
def test_a_failed_fetch_is_omitted_instead_of_raising(session: Session) -> None:
    respx.get(URL_PATTERN).mock(return_value=httpx.Response(500))

    row = persist_movie_releases(
        session, edition_date=EDITION, genre="bollywood", fetcher=fetcher(), api_key="k", now=NOW
    )

    assert row is None
    assert load_movie_releases(session, edition_date=EDITION, genre="bollywood") == []


@respx.mock
def test_a_malformed_response_is_omitted_instead_of_raising(session: Session) -> None:
    respx.get(URL_PATTERN).mock(return_value=httpx.Response(200, json={"unexpected": True}))

    row = persist_movie_releases(
        session, edition_date=EDITION, genre="bollywood", fetcher=fetcher(), api_key="k", now=NOW
    )

    assert row is None


@respx.mock
def test_an_empty_results_list_is_omitted(session: Session) -> None:
    respx.get(URL_PATTERN).mock(return_value=httpx.Response(200, json={"results": []}))

    row = persist_movie_releases(
        session, edition_date=EDITION, genre="bollywood", fetcher=fetcher(), api_key="k", now=NOW
    )

    assert row is None

"""Weather agent: one call per city per edition_date, cached; a missing
reading never raises, only omits the box.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.seed import seed_cities
from app.models.content import WeatherCache
from app.models.users import City
from app.render.email import Weather
from app.services.weather import API_URL, get_weather
from app.sources.fetch import Fetcher

pytestmark = pytest.mark.integration

EDITION = date(2026, 10, 5)
NOW = datetime(2026, 10, 5, 1, 30, tzinfo=UTC)
URL_PATTERN = re.compile(rf"^{re.escape(API_URL)}\?.*")


def fetcher() -> Fetcher:
    """No real sleeping: a failing test would otherwise pay full backoff."""
    clock = [0.0]
    return Fetcher(
        user_agent="TheMorningMosaic/0.1 (+test)",
        sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        monotonic=lambda: clock[0],
    )


def mumbai(session: Session) -> City:
    seed_cities(session)
    session.flush()
    city = session.get(City, "mumbai")
    assert city is not None
    return city


def owm_response(
    *, description: str = "clear sky", low: float = 21.4, high: float = 29.8
) -> dict[str, object]:
    return {
        "weather": [{"description": description}],
        "main": {"temp_min": low, "temp_max": high},
    }


@respx.mock
def test_a_fresh_fetch_is_cached_and_returned(session: Session) -> None:
    city = mumbai(session)
    respx.get(URL_PATTERN).mock(return_value=httpx.Response(200, json=owm_response()))

    weather = get_weather(
        session, city=city, edition_date=EDITION, fetcher=fetcher(), api_key="k", now=NOW
    )

    assert weather == Weather(city="Mumbai", summary="Clear sky", low=21, high=30)
    row = session.scalar(
        select(WeatherCache).where(
            WeatherCache.city_id == "mumbai", WeatherCache.edition_date == EDITION
        )
    )
    assert row is not None
    assert row.provider == "openweathermap"


@respx.mock
def test_a_second_call_for_the_same_city_and_date_does_not_refetch(session: Session) -> None:
    city = mumbai(session)
    route = respx.get(URL_PATTERN).mock(return_value=httpx.Response(200, json=owm_response()))

    get_weather(session, city=city, edition_date=EDITION, fetcher=fetcher(), api_key="k", now=NOW)
    second = get_weather(
        session, city=city, edition_date=EDITION, fetcher=fetcher(), api_key="k", now=NOW
    )

    assert route.call_count == 1
    assert second == Weather(city="Mumbai", summary="Clear sky", low=21, high=30)


@respx.mock
def test_a_failed_fetch_returns_none_instead_of_raising(session: Session) -> None:
    city = mumbai(session)
    respx.get(URL_PATTERN).mock(return_value=httpx.Response(500))

    weather = get_weather(
        session,
        city=city,
        edition_date=EDITION,
        fetcher=fetcher(),
        api_key="k",
        now=NOW,
    )

    assert weather is None
    assert (
        session.scalar(
            select(WeatherCache).where(
                WeatherCache.city_id == "mumbai", WeatherCache.edition_date == EDITION
            )
        )
        is None
    )


@respx.mock
def test_a_malformed_response_returns_none_instead_of_raising(session: Session) -> None:
    city = mumbai(session)
    respx.get(URL_PATTERN).mock(return_value=httpx.Response(200, json={"unexpected": True}))

    weather = get_weather(
        session, city=city, edition_date=EDITION, fetcher=fetcher(), api_key="k", now=NOW
    )

    assert weather is None

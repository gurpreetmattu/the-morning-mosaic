"""Weather agent (agent 7). No LLM: one HTTP call per city, cached once per
city per edition_date in `weather_cache` so N readers in the same city never
cost N API calls, and a later delivery run the same day reuses the morning's
reading instead of calling again.

CLAUDE.md calls this a "forecast," but OpenWeatherMap's actual daily-forecast
product (One Call) needs a separate subscription tier beyond the plain free
API key CLAUDE.md provisions. This uses the always-free Current Weather
endpoint instead — a real reading taken at build time, not a predicted
high/low for the day — and says so here rather than silently claiming more
than it delivers.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import now_utc
from app.models.content import WeatherCache
from app.models.users import City
from app.render.email import Weather
from app.sources.fetch import Fetcher, FetchError

logger = logging.getLogger(__name__)

PROVIDER = "openweathermap"
API_URL = "https://api.openweathermap.org/data/2.5/weather"


class WeatherError(Exception):
    """The reading could not be fetched or did not parse as expected."""


def _fetch_reading(fetcher: Fetcher, *, api_key: str, city: City) -> dict[str, Any]:
    url = f"{API_URL}?lat={city.lat}&lon={city.lon}&appid={api_key}&units=metric"
    try:
        response = fetcher.get(url)
    except FetchError as exc:
        raise WeatherError(f"{city.id}: {exc}") from exc

    try:
        data = response.json()
        description = str(data["weather"][0]["description"]).capitalize()
        low = round(data["main"]["temp_min"])
        high = round(data["main"]["temp_max"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise WeatherError(f"{city.id}: unexpected response shape") from exc

    return {"summary": description, "low": low, "high": high}


def _to_weather(city: City, payload: dict[str, Any]) -> Weather:
    return Weather(
        city=city.name,
        summary=str(payload["summary"]),
        low=int(payload["low"]),
        high=int(payload["high"]),
    )


def _cached(session: Session, *, city: City, edition_date: date) -> WeatherCache | None:
    return session.scalar(
        select(WeatherCache).where(
            WeatherCache.city_id == city.id, WeatherCache.edition_date == edition_date
        )
    )


def get_weather(
    session: Session,
    *,
    city: City,
    edition_date: date,
    fetcher: Fetcher,
    api_key: str,
    now: datetime | None = None,
) -> Weather | None:
    """Today's reading for one city, cached once per city per edition_date.

    Never raises — a missing weather box is cosmetic, not a reason to hold up
    or fail a reader's edition, matching CLAUDE.md's general rule that a
    missing item is acceptable. Only adds/flushes the cache row; the caller's
    own commit boundary (the delivery job already commits once per reader)
    is what actually persists it.
    """
    cached = _cached(session, city=city, edition_date=edition_date)
    if cached is not None:
        return _to_weather(city, cached.payload)

    try:
        payload = _fetch_reading(fetcher, api_key=api_key, city=city)
    except WeatherError:
        logger.warning("weather fetch failed for city=%s", city.id, exc_info=True)
        return None

    session.add(
        WeatherCache(
            city_id=city.id,
            edition_date=edition_date,
            payload=payload,
            provider=PROVIDER,
            fetched_at=now or now_utc(),
        )
    )
    try:
        session.flush()
    except IntegrityError:
        # A concurrent delivery run for the same city won the race; its row
        # is authoritative, not this one — same shape as Delivery.claim().
        session.rollback()
        cached = _cached(session, city=city, edition_date=edition_date)
        if cached is None:
            return None
        return _to_weather(city, cached.payload)

    return _to_weather(city, payload)

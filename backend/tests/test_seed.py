"""Seeding mirrors /config into the reference tables, and is safe to rerun."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.loader import load_cities, load_sources
from app.db.seed import seed_all, seed_cities, seed_sources
from app.models import City, Source

pytestmark = pytest.mark.integration


def test_every_configured_city_is_seeded(session: Session) -> None:
    seed_cities(session)
    session.flush()

    stored = {row.id for row in session.scalars(select(City))}
    configured = {city.id for city in load_cities().cities}
    assert configured <= stored


def test_every_configured_source_is_seeded(session: Session) -> None:
    seed_sources(session)
    session.flush()

    stored = {row.key for row in session.scalars(select(Source))}
    configured = {source.key for source in load_sources().sources}
    assert configured <= stored


def test_sources_arrive_disabled(session: Session) -> None:
    """Nothing may be fetched until a human confirms the outlet's terms."""
    seed_sources(session)
    session.flush()

    enabled = [row.key for row in session.scalars(select(Source)) if row.enabled]
    assert enabled == []


def test_seeding_twice_changes_nothing_the_second_time(session: Session) -> None:
    seed_all(session)
    session.flush()

    second = seed_all(session)
    session.flush()

    assert not second.changed, (
        f"{second.cities.describe('cities')}; {second.sources.describe('sources')}"
    )


def test_an_edited_city_is_updated_in_place(session: Session) -> None:
    seed_cities(session)
    session.flush()

    mumbai = session.get(City, "mumbai")
    assert mumbai is not None
    mumbai.lat = 0.0
    mumbai.active = False
    session.flush()

    result = seed_cities(session)
    session.flush()

    refreshed = session.get(City, "mumbai")
    assert refreshed is not None
    assert refreshed.lat == pytest.approx(19.076, abs=1e-3)
    assert refreshed.active is True
    assert result.updated == 1


def test_a_city_dropped_from_config_is_deactivated_not_deleted(session: Session) -> None:
    """Users hold a foreign key to cities; deleting one would break history."""
    session.add(
        City(id="atlantis", name="Atlantis", state="Nowhere", lat=20.0, lon=80.0, active=True)
    )
    session.flush()

    result = seed_cities(session)
    session.flush()

    survivor = session.get(City, "atlantis")
    assert survivor is not None, "the row must survive"
    assert survivor.active is False
    assert result.deactivated == 1


def test_a_source_dropped_from_config_is_disabled_not_deleted(session: Session) -> None:
    session.add(
        Source(
            key="defunct-wire",
            name="Defunct Wire",
            homepage="https://defunct.example",
            tier=2,
            terms_url="https://defunct.example/terms",
            terms_confirmed=True,
            enabled=True,
        )
    )
    session.flush()

    result = seed_sources(session)
    session.flush()

    survivor = session.scalar(select(Source).where(Source.key == "defunct-wire"))
    assert survivor is not None, "articles reference sources; the row must survive"
    assert survivor.enabled is False
    assert result.deactivated == 1

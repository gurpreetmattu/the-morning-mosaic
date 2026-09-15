"""Seed reference tables from /config.

`cities` and `sources` are mirrors of the YAML, which is the single source of
truth. Seeding is idempotent so it can run on every deploy.

Rows dropped from the YAML are deactivated, never deleted: users reference
cities and articles reference sources, and losing that history would break
the audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.loader import load_cities, load_sources
from app.models import City, Source


@dataclass
class SeedResult:
    added: int = 0
    updated: int = 0
    deactivated: int = 0
    unchanged: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.added or self.updated or self.deactivated)

    def describe(self, what: str) -> str:
        return (
            f"{what}: {self.added} added, {self.updated} updated, "
            f"{self.deactivated} deactivated, {self.unchanged} unchanged"
        )


@dataclass
class SeedSummary:
    cities: SeedResult = field(default_factory=SeedResult)
    sources: SeedResult = field(default_factory=SeedResult)

    @property
    def changed(self) -> bool:
        return self.cities.changed or self.sources.changed


def seed_cities(session: Session) -> SeedResult:
    config = load_cities()
    existing = {row.id: row for row in session.scalars(select(City))}
    result = SeedResult()

    for city in config.cities:
        row = existing.get(city.id)
        if row is None:
            session.add(
                City(
                    id=city.id,
                    name=city.name,
                    state=city.state,
                    lat=city.lat,
                    lon=city.lon,
                    active=True,
                )
            )
            result.added += 1
            continue

        desired = (city.name, city.state, city.lat, city.lon, True)
        current = (row.name, row.state, row.lat, row.lon, row.active)
        if desired == current:
            result.unchanged += 1
            continue

        row.name, row.state, row.lat, row.lon, row.active = desired
        result.updated += 1

    configured = {city.id for city in config.cities}
    for city_id, row in existing.items():
        if city_id not in configured and row.active:
            row.active = False
            result.deactivated += 1

    return result


def seed_sources(session: Session) -> SeedResult:
    config = load_sources()
    existing = {row.key: row for row in session.scalars(select(Source))}
    result = SeedResult()

    for source in config.sources:
        desired = (
            source.name,
            str(source.homepage),
            source.tier,
            str(source.terms_url),
            source.terms_confirmed,
            source.enabled,
        )
        row = existing.get(source.key)
        if row is None:
            session.add(
                Source(
                    key=source.key,
                    name=source.name,
                    homepage=str(source.homepage),
                    tier=source.tier,
                    terms_url=str(source.terms_url),
                    terms_confirmed=source.terms_confirmed,
                    enabled=source.enabled,
                )
            )
            result.added += 1
            continue

        current = (
            row.name,
            row.homepage,
            row.tier,
            row.terms_url,
            row.terms_confirmed,
            row.enabled,
        )
        if desired == current:
            result.unchanged += 1
            continue

        (
            row.name,
            row.homepage,
            row.tier,
            row.terms_url,
            row.terms_confirmed,
            row.enabled,
        ) = desired
        result.updated += 1

    configured = {source.key for source in config.sources}
    for key, row in existing.items():
        # A source removed from the whitelist must stop being fetched, but its
        # articles stay, so the row is disabled rather than dropped.
        if key not in configured and row.enabled:
            row.enabled = False
            result.deactivated += 1

    return result


def seed_all(session: Session) -> SeedSummary:
    return SeedSummary(cities=seed_cities(session), sources=seed_sources(session))

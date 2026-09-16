"""Public, read-only configuration the frontend needs to build its forms.

CLAUDE.md: "the frontend only talks to the FastAPI backend, never directly to
the database." Genres, delivery slots, and the frequency/edition-preference
choices come straight from `config/*.yaml` (no database round trip); cities
are a database table (seeded from `config/cities.yaml`, see `app/db/seed.py`)
because a city can be deactivated without touching the YAML. Either way, this
is the one place a client learns what a valid signup or preferences payload
looks like, so the signup form never hand-codes a duplicate of the genre
list or the 87 cities.
"""

from __future__ import annotations

from datetime import time as clock_time
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.config.loader import load_genres
from app.models.users import DELIVERY_SLOTS, City

router = APIRouter()

FREQUENCIES = ("daily", "weekdays")
EDITION_PREFERENCES = ("india", "global", "mixed")


class GenreOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    display_name: str
    blurb: str


class CityOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    state: str


class ConfigResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    genres: list[GenreOption]
    cities: list[CityOption]
    delivery_slots: list[clock_time]
    frequencies: list[str]
    edition_preferences: list[str]


@router.get("/api/config", response_model=ConfigResponse)
def read_config(session: Annotated[Session, Depends(db_session)]) -> ConfigResponse:
    genres = [
        GenreOption(key=genre.key, display_name=genre.display_name, blurb=genre.blurb)
        for genre in load_genres().genres
    ]
    cities = [
        CityOption(id=row.id, name=row.name, state=row.state)
        for row in session.scalars(select(City).where(City.active.is_(True)).order_by(City.name))
    ]
    return ConfigResponse(
        genres=genres,
        cities=cities,
        delivery_slots=[clock_time.fromisoformat(slot) for slot in DELIVERY_SLOTS],
        frequencies=list(FREQUENCIES),
        edition_preferences=list(EDITION_PREFERENCES),
    )

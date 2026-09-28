"""Load and validate the YAML files in /config.

Each loader is cached for the process lifetime: config is read once per job run.
"""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.config.schemas import (
    CitiesConfig,
    EditionsConfig,
    GenresConfig,
    ModelsConfig,
    SourcesConfig,
)

CONFIG_DIR_ENV = "CONFIG_DIR"
# Dev/test-only escape hatch: lets local testing use any edition_date without
# editing the committed, still-PROVISIONAL launch_date in editions.yaml, and
# without that placeholder blocking `run_build` (see
# Orchestrator.edition_number). editions.yaml's own launch_date stays the one
# real value that actually gates going live — set only once, when the owner
# is ready. Never honoured in prod: a launch date silently overridden there
# would desync edition numbering from what was actually sent.
LAUNCH_DATE_OVERRIDE_ENV = "EDITION_LAUNCH_DATE_OVERRIDE"


def config_dir() -> Path:
    override = os.getenv(CONFIG_DIR_ENV)
    if override:
        return Path(override)
    # backend/app/config/loader.py -> repo root
    return Path(__file__).resolve().parents[3] / "config"


def _load[T: BaseModel](filename: str, model: type[T]) -> T:
    path = config_dir() / filename
    if not path.is_file():
        raise FileNotFoundError(f"missing config file: {path}")
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return model.model_validate(raw)


@lru_cache(maxsize=1)
def load_genres() -> GenresConfig:
    return _load("genres.yaml", GenresConfig)


@lru_cache(maxsize=1)
def load_sources() -> SourcesConfig:
    return _load("sources.yaml", SourcesConfig)


@lru_cache(maxsize=1)
def load_models() -> ModelsConfig:
    return _load("models.yaml", ModelsConfig)


@lru_cache(maxsize=1)
def load_editions() -> EditionsConfig:
    config = _load("editions.yaml", EditionsConfig)
    override = os.getenv(LAUNCH_DATE_OVERRIDE_ENV)
    if override:
        if os.getenv("APP_ENV", "dev") == "prod":
            raise RuntimeError(
                f"{LAUNCH_DATE_OVERRIDE_ENV} is set in prod; remove it — "
                "editions.yaml's own launch_date is the only real launch date."
            )
        config = config.model_copy(update={"launch_date": date.fromisoformat(override)})
    return config


@lru_cache(maxsize=1)
def load_cities() -> CitiesConfig:
    return _load("cities.yaml", CitiesConfig)


def clear_cache() -> None:
    """Drop cached config. Used by tests that point CONFIG_DIR elsewhere."""
    for loader in (load_genres, load_sources, load_models, load_editions, load_cities):
        loader.cache_clear()

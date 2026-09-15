"""Load and validate the YAML files in /config.

Each loader is cached for the process lifetime: config is read once per job run.
"""

from __future__ import annotations

import os
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
    return _load("editions.yaml", EditionsConfig)


@lru_cache(maxsize=1)
def load_cities() -> CitiesConfig:
    return _load("cities.yaml", CitiesConfig)


def clear_cache() -> None:
    """Drop cached config. Used by tests that point CONFIG_DIR elsewhere."""
    for loader in (load_genres, load_sources, load_models, load_editions, load_cities):
        loader.cache_clear()

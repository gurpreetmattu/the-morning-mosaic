"""Pydantic schemas for the YAML files in /config.

Every file in /config is validated against these models at load time. Invalid
configuration fails loudly at startup rather than producing a broken edition.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, get_args
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

GenreKey = Literal[
    "india",
    "politics",
    "business",
    "technology",
    "ai",
    "sports",
    "gaming",
    "bollywood",
    "hollywood",
    "music",
]
GENRE_KEYS: tuple[GenreKey, ...] = get_args(GenreKey)

AgentKey = Literal["orchestrator", "ranker", "writer", "fact_checker", "image_finder"]
AGENT_KEYS: tuple[AgentKey, ...] = get_args(AgentKey)

# Agents whose model must be pinned rather than failed over (see CLAUDE.md).
PINNED_AGENTS: frozenset[AgentKey] = frozenset({"writer", "fact_checker"})

# Placeholder in models.yaml until a real model id has been chosen.
UNSET_MODEL = "REPLACE_WITH_A_REAL_MODEL_ID"

ExtraKind = Literal[
    "scores_fixtures",
    "movie_releases",
    "music_releases",
    "ai_tool_of_the_day",
    "game_deals",
]

# "strict" genres need >=2 independent tier-1/2 sources, or one primary source.
Corroboration = Literal["standard", "strict"]

HexColor = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$", min_length=2, max_length=64)]

# Rough bounding box of India, including island territories.
INDIA_LAT_MIN, INDIA_LAT_MAX = 6.0, 37.6
INDIA_LON_MIN, INDIA_LON_MAX = 67.9, 97.5


class ConfigBase(BaseModel):
    """Immutable, typo-intolerant base for every config model."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return sorted(dupes)


# --------------------------------------------------------------------------- genres


class Theme(ConfigBase):
    accent: HexColor
    accent_soft: HexColor
    rule: HexColor
    heading_font: str
    body_font: str


class Genre(ConfigBase):
    key: GenreKey
    display_name: str
    section_title: str
    blurb: str
    theme: Theme
    corroboration: Corroboration
    topic_tags: list[Slug] = Field(min_length=4)
    extras: list[ExtraKind] = Field(default_factory=list)
    pool_size: int = Field(default=10, ge=1, le=20)
    min_stories: int = Field(default=2, ge=1)
    max_stories: int = Field(default=6, ge=1)

    @model_validator(mode="after")
    def _check(self) -> Genre:
        dupes = _duplicates(self.topic_tags)
        if dupes:
            raise ValueError(f"genre {self.key}: duplicate topic tags {dupes}")
        if self.min_stories > self.max_stories:
            raise ValueError(f"genre {self.key}: min_stories exceeds max_stories")
        if self.max_stories > self.pool_size:
            raise ValueError(f"genre {self.key}: max_stories exceeds pool_size")
        return self


class GenresConfig(ConfigBase):
    genres: list[Genre]

    @model_validator(mode="after")
    def _check(self) -> GenresConfig:
        keys = [genre.key for genre in self.genres]
        dupes = _duplicates(list(keys))
        if dupes:
            raise ValueError(f"duplicate genre keys {dupes}")
        missing = sorted(set(GENRE_KEYS) - set(keys))
        if missing:
            raise ValueError(f"missing genre definitions {missing}")
        return self

    def by_key(self) -> dict[GenreKey, Genre]:
        return {genre.key: genre for genre in self.genres}

    def topic_tags(self, key: GenreKey) -> frozenset[str]:
        return frozenset(self.by_key()[key].topic_tags)


# -------------------------------------------------------------------------- sources


class Feed(ConfigBase):
    """One RSS/Atom feed and the genres its items belong to."""

    url: HttpUrl
    genres: list[GenreKey] = Field(min_length=1)


class Source(ConfigBase):
    key: Slug
    name: str
    homepage: HttpUrl
    feeds: list[Feed] = Field(min_length=1)
    tier: Literal[1, 2, 3]
    terms_url: HttpUrl
    terms_confirmed: bool = False
    robots_checked: bool = False
    enabled: bool = False
    notes: str | None = None
    # An explicit, per-source exception to "a naive timestamp is never
    # guessed at" (app/sources/freshness.py): some feeds (RBI's, so far)
    # publish a pubDate with no timezone offset, which feedparser then
    # cannot parse at all. Set only when this source's own timezone is
    # actually known — a government institution's own press timestamps,
    # not a guess about the content — never as a blanket default.
    fallback_timezone: str | None = None

    @property
    def genres(self) -> frozenset[GenreKey]:
        return frozenset(genre for feed in self.feeds for genre in feed.genres)

    @field_validator("fallback_timezone")
    @classmethod
    def _valid_timezone(cls, value: str | None) -> str | None:
        if value is not None and value not in available_timezones():
            raise ValueError(f"{value!r} is not a known IANA timezone")
        return value

    @model_validator(mode="after")
    def _check(self) -> Source:
        # A source may only be fetched once a human has confirmed its terms
        # permit display in an email newsletter, and that robots.txt allows it.
        if self.enabled and not (self.terms_confirmed and self.robots_checked):
            raise ValueError(
                f"source {self.key}: enabled requires terms_confirmed and robots_checked"
            )
        dupes = _duplicates([str(feed.url) for feed in self.feeds])
        if dupes:
            raise ValueError(f"source {self.key}: duplicate feeds {dupes}")
        return self


class SourcesConfig(ConfigBase):
    sources: list[Source]

    @model_validator(mode="after")
    def _check(self) -> SourcesConfig:
        dupes = _duplicates([source.key for source in self.sources])
        if dupes:
            raise ValueError(f"duplicate source keys {dupes}")
        urls = _duplicates([str(feed.url) for source in self.sources for feed in source.feeds])
        if urls:
            raise ValueError(f"feed url used by more than one source {urls}")
        return self

    def enabled_for(self, genre: GenreKey) -> list[Source]:
        return [s for s in self.sources if s.enabled and genre in s.genres]

    def feeds_for(self, genre: GenreKey) -> list[tuple[Source, Feed]]:
        return [
            (source, feed)
            for source in self.sources
            if source.enabled
            for feed in source.feeds
            if genre in feed.genres
        ]


# --------------------------------------------------------------------------- models


class ModelSpec(ConfigBase):
    model: str
    temperature: float = Field(ge=0.0, le=2.0)
    max_output_tokens: int = Field(gt=0)
    pinned: bool = False
    fallbacks: list[str] = Field(default_factory=list)
    # The model id to use on the configured fallback gateway (LLM_FALLBACK_URL),
    # since a fallback provider is a different vendor with its own model
    # names — reusing `model`/`fallbacks` there would just 404. None means
    # "no fallback gateway route for this agent" even if one is configured.
    fallback_model: str | None = None

    @property
    def is_configured(self) -> bool:
        """False while the model id is still the placeholder from the repo."""
        ids = {self.model, *self.fallbacks}
        if self.fallback_model:
            ids.add(self.fallback_model)
        return UNSET_MODEL not in ids

    @model_validator(mode="after")
    def _check(self) -> ModelSpec:
        if self.pinned and (self.fallbacks or self.fallback_model):
            raise ValueError("a pinned model must not declare fallbacks")
        return self


class ModelsConfig(ConfigBase):
    request_timeout_seconds: float = Field(gt=0)
    max_attempts: int = Field(ge=1)
    agents: dict[AgentKey, ModelSpec]

    @model_validator(mode="after")
    def _check(self) -> ModelsConfig:
        missing = sorted(set(AGENT_KEYS) - set(self.agents))
        if missing:
            raise ValueError(f"missing model config for agents {missing}")
        for agent in sorted(PINNED_AGENTS):
            if not self.agents[agent].pinned:
                raise ValueError(f"agent {agent} must use a pinned model")
        return self


# ------------------------------------------------------------------------- editions


class WeekendConfig(ConfigBase):
    saturday_features: list[Slug] = Field(min_length=1)
    sunday_features: list[Slug] = Field(min_length=1)


class SpecialEdition(ConfigBase):
    key: Slug
    name: str
    # Not `on`: YAML 1.1 parses a bare `on` key as the boolean true.
    observed_on: date
    note: str
    accent: HexColor | None = None


class EditionsConfig(ConfigBase):
    launch_date: date
    weekend: WeekendConfig
    special_editions: list[SpecialEdition] = Field(default_factory=list)
    # Festivals whose dates move each year and have not been confirmed yet.
    # Listed so the yearly calendar update has an explicit checklist.
    awaiting_dates: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> EditionsConfig:
        dupes = _duplicates([edition.key for edition in self.special_editions])
        if dupes:
            raise ValueError(f"duplicate special edition keys {dupes}")
        clashes = _duplicates([e.observed_on.isoformat() for e in self.special_editions])
        if clashes:
            raise ValueError(f"more than one special edition on {clashes}")
        return self

    def for_date(self, day: date) -> SpecialEdition | None:
        for edition in self.special_editions:
            if edition.observed_on == day:
                return edition
        return None

    def by_key(self, key: str) -> SpecialEdition | None:
        return next((edition for edition in self.special_editions if edition.key == key), None)

    def covered_years(self) -> frozenset[int]:
        return frozenset(e.observed_on.year for e in self.special_editions)


# --------------------------------------------------------------------------- cities


class City(ConfigBase):
    id: Slug
    name: str
    state: str
    lat: float = Field(ge=INDIA_LAT_MIN, le=INDIA_LAT_MAX)
    lon: float = Field(ge=INDIA_LON_MIN, le=INDIA_LON_MAX)


class CitiesConfig(ConfigBase):
    cities: list[City]

    @model_validator(mode="after")
    def _check(self) -> CitiesConfig:
        dupes = _duplicates([city.id for city in self.cities])
        if dupes:
            raise ValueError(f"duplicate city ids {dupes}")
        labels = _duplicates([f"{city.name}, {city.state}" for city in self.cities])
        if labels:
            raise ValueError(f"duplicate city names {labels}")
        return self

    def by_id(self) -> dict[str, City]:
        return {city.id: city for city in self.cities}

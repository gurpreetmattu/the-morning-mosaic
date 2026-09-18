"""The shipped /config must load, and the safety validators must actually bite."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.config import (
    load_cities,
    load_editions,
    load_genres,
    load_models,
    load_sources,
)
from app.config.schemas import (
    AGENT_KEYS,
    GENRE_KEYS,
    PINNED_AGENTS,
    City,
    GenresConfig,
    ModelSpec,
    Source,
)
from app.config.settings import Settings


def _theme() -> dict[str, str]:
    return {
        "accent": "#112233",
        "accent_soft": "#eeeeee",
        "rule": "#cccccc",
        "heading_font": "Georgia, serif",
        "body_font": "Georgia, serif",
    }


def _genre(key: str) -> dict[str, Any]:
    return {
        "key": key,
        "display_name": key.title(),
        "section_title": key.title(),
        "blurb": "b",
        "corroboration": "standard",
        "theme": _theme(),
        "topic_tags": ["one", "two", "three", "four"],
    }


def _source(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "key": "example",
        "name": "Example",
        "homepage": "https://example.com/",
        "tier": 2,
        "terms_url": "https://example.com/terms",
        "feeds": [{"url": "https://example.com/feed", "genres": ["india"]}],
    }
    return base | overrides


# ----------------------------------------------------------- the shipped config


def test_every_config_file_loads() -> None:
    assert load_genres().genres
    assert load_sources().sources
    assert load_models().agents
    assert load_cities().cities
    assert load_editions().launch_date


def test_all_ten_genres_are_defined() -> None:
    assert set(load_genres().by_key()) == set(GENRE_KEYS)


def test_strict_corroboration_applies_to_india_politics_business() -> None:
    by_key = load_genres().by_key()
    for key in ("india", "politics", "business"):
        assert by_key[key].corroboration == "strict"


def test_no_source_is_enabled_without_confirmed_terms() -> None:
    for source in load_sources().sources:
        if source.enabled:
            assert source.terms_confirmed and source.robots_checked, source.key


def test_every_source_feed_targets_a_known_genre() -> None:
    known = set(GENRE_KEYS)
    for source in load_sources().sources:
        assert source.genres <= known, source.key


def test_every_genre_has_at_least_one_candidate_source() -> None:
    covered = {genre for source in load_sources().sources for genre in source.genres}
    assert set(GENRE_KEYS) - covered == set()


def test_pinned_agents_are_pinned_and_have_no_fallbacks() -> None:
    agents = load_models().agents
    assert set(agents) == set(AGENT_KEYS)
    for key in PINNED_AGENTS:
        assert agents[key].pinned
        assert agents[key].fallbacks == []


def test_special_editions_are_looked_up_by_date() -> None:
    editions = load_editions()
    first = editions.special_editions[0]
    assert editions.for_date(first.observed_on) is first
    assert editions.for_date(date(1999, 1, 1)) is None


def test_special_editions_are_looked_up_by_key() -> None:
    editions = load_editions()
    first = editions.special_editions[0]
    assert editions.by_key(first.key) is first
    assert editions.by_key("not-a-real-key") is None


def test_cities_are_unique_and_addressable() -> None:
    cities = load_cities()
    assert len(cities.by_id()) == len(cities.cities)
    assert "mumbai" in cities.by_id()


# ------------------------------------------------------------------- validators


def test_missing_genre_is_rejected() -> None:
    with pytest.raises(ValidationError, match="missing genre definitions"):
        GenresConfig.model_validate({"genres": [_genre("india")]})


def test_duplicate_topic_tags_are_rejected() -> None:
    payload = _genre("india") | {"topic_tags": ["markets", "markets", "trade", "energy"]}
    with pytest.raises(ValidationError, match="duplicate topic tags"):
        GenresConfig.model_validate({"genres": [payload]})


def test_source_cannot_be_enabled_without_terms_and_robots() -> None:
    with pytest.raises(ValidationError, match="terms_confirmed and robots_checked"):
        Source.model_validate(_source(enabled=True, terms_confirmed=True))


def test_source_may_be_enabled_once_both_checks_pass() -> None:
    source = Source.model_validate(_source(enabled=True, terms_confirmed=True, robots_checked=True))
    assert source.enabled


def test_a_source_needs_no_fallback_timezone_by_default() -> None:
    assert Source.model_validate(_source()).fallback_timezone is None


def test_a_real_iana_timezone_is_accepted() -> None:
    source = Source.model_validate(_source(fallback_timezone="Asia/Kolkata"))
    assert source.fallback_timezone == "Asia/Kolkata"


def test_an_unknown_timezone_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="not a known IANA timezone"):
        Source.model_validate(_source(fallback_timezone="Not/A_Zone"))


def test_pinned_model_may_not_declare_fallbacks() -> None:
    with pytest.raises(ValidationError, match="must not declare fallbacks"):
        ModelSpec.model_validate(
            {
                "model": "m",
                "temperature": 0.0,
                "max_output_tokens": 128,
                "pinned": True,
                "fallbacks": ["other"],
            }
        )


def test_a_fallback_model_requires_the_primary_gateway() -> None:
    with pytest.raises(ValidationError, match="fallback_model requires gateway: primary"):
        ModelSpec.model_validate(
            {
                "model": "m",
                "temperature": 0.0,
                "max_output_tokens": 128,
                "pinned": False,
                "gateway": "fallback",
                "fallback_model": "other",
            }
        )


def test_a_pinned_agent_may_sit_on_the_fallback_gateway() -> None:
    spec = ModelSpec.model_validate(
        {
            "model": "m",
            "temperature": 0.0,
            "max_output_tokens": 128,
            "pinned": True,
            "gateway": "fallback",
        }
    )
    assert spec.gateway == "fallback"


def test_pinned_model_may_not_declare_a_fallback_model() -> None:
    with pytest.raises(ValidationError, match="must not declare fallbacks"):
        ModelSpec.model_validate(
            {
                "model": "m",
                "temperature": 0.0,
                "max_output_tokens": 128,
                "pinned": True,
                "fallback_model": "other",
            }
        )


def test_city_outside_india_is_rejected() -> None:
    with pytest.raises(ValidationError):
        City.model_validate(
            {"id": "paris", "name": "Paris", "state": "x", "lat": 48.85, "lon": 2.35}
        )


# --------------------------------------------------------------------- settings


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "base_url": "https://example.com",
        "database_url": "postgresql://u:p@localhost/db",
        "smtp_host": "smtp.example.com",
        "sender_email": "news@example.com",
        "sender_name": "Example",
        "gmail_app_password": "secret",
        "imap_host": "imap.example.com",
        "admin_email": "admin@example.com",
        "llm_gateway_url": "https://llm.example.com",
        "llm_gateway_api_key": "secret",
        "token_signing_key": "secret",
    }
    # model_validate bypasses the env/.env sources, so a developer's local .env
    # cannot change the outcome of these tests.
    return Settings.model_validate(base | overrides)


def test_dev_sending_is_restricted_to_the_allowlist() -> None:
    settings = _settings(app_env="dev", test_email_allowlist="a@x.test, B@X.test")
    assert settings.may_send_to("a@x.test")
    assert settings.may_send_to("b@x.test")
    assert not settings.may_send_to("stranger@x.test")


def test_dev_with_an_empty_allowlist_sends_to_nobody() -> None:
    assert not _settings(app_env="dev").may_send_to("anyone@x.test")


def test_prod_is_not_allowlisted() -> None:
    settings = _settings(app_env="prod", test_email_allowlist="a@x.test")
    assert settings.may_send_to("anyone@x.test")
    assert settings.allowlisted_test_emails == frozenset()


def test_secrets_do_not_leak_into_repr() -> None:
    sentinel = "n0t-in-any-log"
    settings = _settings(gmail_app_password=sentinel, token_signing_key=sentinel)
    assert sentinel not in repr(settings)
    assert sentinel not in str(settings.model_dump())
    assert settings.gmail_app_password.get_secret_value() == sentinel

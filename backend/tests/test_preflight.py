"""The pre-flight check must flag what would break a production deploy, and
must never print a secret value."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import preflight
from app.preflight import Level, Report

BASE_ENV = {
    "APP_ENV": "prod",
    "BASE_URL": "https://mosaic.example.run.app",
    "DATABASE_URL": "postgresql://u:s3cretpw@ep-x-pooler.neon.tech/db?sslmode=require",
    "DATABASE_DIRECT_URL": "postgresql://u:s3cretpw@ep-x.neon.tech/db?sslmode=require",
    "SMTP_HOST": "smtp.gmail.com",
    "SENDER_EMAIL": "news@gmail.com",
    "SENDER_NAME": "The Morning Mosaic",
    "GMAIL_APP_PASSWORD": "app-pass-secret-value",
    "IMAP_HOST": "imap.gmail.com",
    "ADMIN_EMAIL": "admin@example.com",
    "LLM_GATEWAY_URL": "https://api.groq.com/openai/v1",
    "LLM_GATEWAY_API_KEY": "llm-secret-value",
    "TOKEN_SIGNING_KEY": "k" * 48,
    "TURNSTILE_SITE_KEY": "site",
    "TURNSTILE_SECRET_KEY": "turnstile-secret-value",
    "GCP_PROJECT_ID": "proj",
    "GCS_PDF_BUCKET": "bucket",
}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    monkeypatch.chdir(tmp_path)  # no stray .env
    for key in list(__import__("os").environ):
        if key in BASE_ENV or key.startswith(("LLM_", "TEST_EMAIL", "EDITION_", "MAX_")):
            monkeypatch.delenv(key)
    for key, value in BASE_ENV.items():
        monkeypatch.setenv(key, value)
    return monkeypatch


def levels(report: Report) -> dict[str, Level]:
    return {check.name: check.level for check in report.checks}


def test_a_valid_prod_environment_has_no_failures(env: pytest.MonkeyPatch) -> None:
    report = preflight.run(live=False, prod_mode=True)
    failures = [c for c in report.checks if c.level is Level.FAIL]
    assert failures == [] or all("launch_date" in c.name for c in failures)


@pytest.mark.parametrize(
    ("key", "value", "check"),
    [
        ("APP_ENV", "dev", "APP_ENV is prod"),
        ("BASE_URL", "http://localhost:8000", "BASE_URL is a public https origin"),
        ("TOKEN_SIGNING_KEY", "short", "TOKEN_SIGNING_KEY is long and non-placeholder"),
        ("TURNSTILE_SECRET_KEY", "", "Turnstile site key and secret are set"),
        ("GCS_PDF_BUCKET", "", "GCP_PROJECT_ID and GCS_PDF_BUCKET are set"),
        ("LLM_GATEWAY_URL", "http://127.0.0.1:8080/v1", "LLM_GATEWAY_URL is publicly reachable"),
        (
            "DATABASE_DIRECT_URL",
            "",
            "DATABASE_DIRECT_URL set for a pooled DATABASE_URL",
        ),
        ("MAX_ACTIVE_SUBSCRIBERS", "450", "MAX_ACTIVE_SUBSCRIBERS leaves room under Gmail's quota"),
    ],
)
def test_prod_mode_fails_each_unsafe_value(
    env: pytest.MonkeyPatch, key: str, value: str, check: str
) -> None:
    env.setenv(key, value)
    assert levels(preflight.run(live=False, prod_mode=True))[check] is Level.FAIL


def test_the_same_problem_is_only_a_warning_outside_prod_mode(env: pytest.MonkeyPatch) -> None:
    env.setenv("BASE_URL", "http://localhost:8000")
    assert (
        levels(preflight.run(live=False, prod_mode=False))["BASE_URL is a public https origin"]
        is Level.WARN
    )


def test_launch_date_override_is_flagged(env: pytest.MonkeyPatch) -> None:
    env.setenv("EDITION_LAUNCH_DATE_OVERRIDE", "2026-01-01")
    assert levels(preflight.run(live=False, prod_mode=True))[
        "EDITION_LAUNCH_DATE_OVERRIDE unset"
    ] is (Level.FAIL)


def test_half_configured_fallback_is_a_failure(env: pytest.MonkeyPatch) -> None:
    env.setenv("LLM_FALLBACK_URL", "https://fallback.example/v1")
    assert levels(preflight.run(live=False, prod_mode=False))[
        "LLM_FALLBACK_URL / LLM_FALLBACK_API_KEY"
    ] is (Level.FAIL)


def test_missing_required_settings_are_named_without_values(env: pytest.MonkeyPatch) -> None:
    env.delenv("GMAIL_APP_PASSWORD")
    report = preflight.run(live=False, prod_mode=True)
    assert report.failed
    assert "setting GMAIL_APP_PASSWORD" in levels(report)


def test_no_secret_value_ever_appears_in_the_output(env: pytest.MonkeyPatch) -> None:
    rendered = preflight.run(live=False, prod_mode=True).render()
    for secret in (
        "s3cretpw",
        "app-pass-secret-value",
        "llm-secret-value",
        "turnstile-secret-value",
    ):
        assert secret not in rendered


def test_main_exit_code_follows_failures(
    env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    env.setenv("APP_ENV", "dev")
    assert preflight.main(["--prod"]) == 1
    assert "[FAIL] APP_ENV is prod" in capsys.readouterr().out

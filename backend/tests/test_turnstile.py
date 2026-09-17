"""verify_turnstile: an unconfigured secret must be indistinguishable from
a blank one.

A real .env can have TURNSTILE_SECRET_KEY= with nothing after the `=`
(present, but empty) rather than the line being absent entirely.
pydantic-settings resolves the first case to SecretStr(""), not None, so
`secret is None` alone does not catch it — found by a real signup failing
locally with a freshly-populated .env that had never set a Turnstile
secret.
"""

from __future__ import annotations

import httpx
import respx

from app.api.security import TURNSTILE_VERIFY_URL, TurnstileError, verify_turnstile
from app.config.settings import Settings


def settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "base_url": "https://mosaic.example.com",
        "database_url": "postgresql://u:p@localhost/db",
        "smtp_host": "smtp.example.com",
        "sender_email": "news@example.com",
        "sender_name": "The Morning Mosaic",
        "gmail_app_password": "x",
        "imap_host": "imap.example.com",
        "admin_email": "admin@example.com",
        "llm_gateway_url": "http://127.0.0.1:8080/v1",
        "llm_gateway_api_key": "x",
        "token_signing_key": "x",
        "app_env": "dev",
    }
    return Settings.model_validate(base | overrides)


async def test_an_absent_secret_skips_the_check_outside_prod() -> None:
    assert await verify_turnstile(None, settings=settings(turnstile_secret_key=None)) is True


async def test_a_blank_but_present_secret_also_skips_outside_prod() -> None:
    """The actual bug: TURNSTILE_SECRET_KEY= with nothing after the `=`
    resolves to SecretStr(""), not None."""
    assert await verify_turnstile(None, settings=settings(turnstile_secret_key="")) is True


async def test_an_absent_secret_in_prod_raises_rather_than_skipping() -> None:
    subject = settings(turnstile_secret_key=None, app_env="prod")
    try:
        await verify_turnstile("some-token", settings=subject)
    except TurnstileError:
        pass
    else:
        raise AssertionError("expected TurnstileError")


async def test_a_blank_secret_in_prod_also_raises() -> None:
    subject = settings(turnstile_secret_key="", app_env="prod")
    try:
        await verify_turnstile("some-token", settings=subject)
    except TurnstileError:
        pass
    else:
        raise AssertionError("expected TurnstileError")


@respx.mock
async def test_a_configured_secret_actually_calls_cloudflare() -> None:
    route = respx.post(TURNSTILE_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    subject = settings(turnstile_secret_key="real-secret")

    assert await verify_turnstile("a-token", settings=subject) is True
    assert route.called


@respx.mock
async def test_a_configured_secret_rejects_a_missing_token() -> None:
    """No network call should happen at all: there is nothing to verify."""
    route = respx.post(TURNSTILE_VERIFY_URL).mock(return_value=httpx.Response(200))
    subject = settings(turnstile_secret_key="real-secret")

    assert await verify_turnstile(None, settings=subject) is False
    assert not route.called

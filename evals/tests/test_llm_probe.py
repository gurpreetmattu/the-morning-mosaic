from __future__ import annotations

import httpx
import respx

from app.config.settings import Settings
from evals.llm_probe import llm_gateway_reachable


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
        "llmbuffet_url": "http://127.0.0.1:8080/v1",
        "llmbuffet_api_key": "x",
        "token_signing_key": "x",
    }
    return Settings.model_validate(base | overrides)


@respx.mock
def test_reachable_when_the_gateway_answers() -> None:
    respx.get("http://127.0.0.1:8080/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    assert llm_gateway_reachable(settings()) is True


@respx.mock
def test_reachable_even_on_a_client_error() -> None:
    """A 401/404 means something answered HTTP; that's not "unreachable"."""
    respx.get("http://127.0.0.1:8080/v1/models").mock(return_value=httpx.Response(404))
    assert llm_gateway_reachable(settings()) is True


@respx.mock
def test_unreachable_on_a_server_error() -> None:
    respx.get("http://127.0.0.1:8080/v1/models").mock(return_value=httpx.Response(503))
    assert llm_gateway_reachable(settings()) is False


@respx.mock
def test_unreachable_on_a_connection_failure() -> None:
    respx.get("http://127.0.0.1:8080/v1/models").mock(side_effect=httpx.ConnectError("refused"))
    assert llm_gateway_reachable(settings()) is False


def test_unreachable_when_nothing_is_listening() -> None:
    # No mock at all: a real connection attempt to a closed port.
    assert llm_gateway_reachable(settings(llmbuffet_url="http://127.0.0.1:1")) is False

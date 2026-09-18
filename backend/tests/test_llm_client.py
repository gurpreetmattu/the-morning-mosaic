"""Routing, retry, and the personal-data guard.

No network and no credentials: respx intercepts the requests the client makes
to the OpenAI-compatible endpoint.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from app.config.schemas import UNSET_MODEL, ModelsConfig
from app.config.settings import Settings
from app.llm.client import LlmClient, Message
from app.llm.errors import (
    LlmConfigurationError,
    LlmUnavailableError,
    PersonalDataInPromptError,
)

PRIMARY = "https://primary.llm"
FALLBACK = "https://fallback.llm"
SECONDARY = "https://secondary.llm"

PROMPT = [Message(role="user", content="Summarise the following passage.")]


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "base_url": "https://example.com",
        "database_url": "postgresql://u:p@localhost/db",
        "smtp_host": "smtp.example.com",
        "sender_email": "news@example.com",
        "sender_name": "Example",
        "gmail_app_password": "x",
        "imap_host": "imap.example.com",
        "admin_email": "admin@example.com",
        "llm_gateway_url": PRIMARY,
        "llm_gateway_api_key": "primary-key",
        "token_signing_key": "x",
    }
    return Settings.model_validate(base | overrides)


def with_fallback_provider() -> Settings:
    return settings(llm_fallback_url=FALLBACK, llm_fallback_api_key="fallback-key")


def with_secondary_provider() -> Settings:
    return settings(llm_secondary_url=SECONDARY, llm_secondary_api_key="secondary-key")


def models(**agent_overrides: Any) -> ModelsConfig:
    def spec(
        model: str,
        pinned: bool,
        fallbacks: list[str] | None = None,
        fallback_model: str | None = None,
        gateway: str = "primary",
        availability_fallback_model: str | None = None,
        availability_fallback_gateway: str | None = None,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "temperature": 0.0,
            "max_output_tokens": 256,
            "pinned": pinned,
            "fallbacks": fallbacks or [],
            "fallback_model": fallback_model,
            "gateway": gateway,
            "availability_fallback_model": availability_fallback_model,
            "availability_fallback_gateway": availability_fallback_gateway,
        }

    agents: dict[str, Any] = {
        "orchestrator": spec("orch-1", False),
        "ranker": spec("rank-1", False, ["rank-2"], fallback_model="rank-fb"),
        "writer": spec("write-1", True),
        "fact_checker": spec("check-1", True),
        "image_finder": spec("image-1", False),
    }
    agents.update(agent_overrides)
    return ModelsConfig.model_validate(
        {"request_timeout_seconds": 5.0, "max_attempts": 3, "agents": agents}
    )


def completion(content: str = "a summary") -> dict[str, Any]:
    return {
        "id": "cmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "m",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }


class Recorder:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.entries.append(kwargs)


def client(
    *,
    setting: Settings | None = None,
    model_config: ModelsConfig | None = None,
    recorder: Any = None,
) -> LlmClient:
    slept: list[float] = []
    return LlmClient(
        settings=setting or settings(),
        models=model_config or models(),
        recorder=recorder,
        sleep=slept.append,
    )


def requested_models() -> list[str]:
    return [json.loads(call.request.content)["model"] for call in respx.calls]


# ----------------------------------------------------------------- happy path


@respx.mock
def test_a_successful_call_returns_text_and_usage() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=httpx.Response(200, json=completion("hello"))
    )
    result = client().complete("ranker", PROMPT)

    assert result.text == "hello"
    assert result.model == "rank-1"
    assert result.provider == "primary"
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 7
    assert result.attempts == 1


@respx.mock
def test_json_object_mode_is_requested_when_asked() -> None:
    route = respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=httpx.Response(200, json=completion("{}"))
    )
    client().complete("ranker", PROMPT, json_object=True)

    body = json.loads(route.calls[0].request.content)
    assert body["response_format"] == {"type": "json_object"}


# -------------------------------------------------------------------- routing


def test_a_pinned_agent_gets_exactly_one_route() -> None:
    routes = client(setting=with_fallback_provider()).routes_for("writer")
    assert [(r.model, r.provider) for r in routes] == [("write-1", "primary")]


def test_an_unpinned_agent_routes_through_models_then_its_fallback_gateway_model() -> None:
    """The fallback gateway is a different vendor with its own model names,
    so it gets one route at its own configured `fallback_model` — never the
    primary gateway's `model`/`fallbacks` list, which would 404 there."""
    routes = client(setting=with_fallback_provider()).routes_for("ranker")
    assert [(r.model, r.provider) for r in routes] == [
        ("rank-1", "primary"),
        ("rank-2", "primary"),
        ("rank-fb", "fallback"),
    ]


def test_a_pinned_agent_can_be_routed_through_the_fallback_gateway_instead() -> None:
    """Writer's real use case: pinned to one route, but that route is the
    fallback gateway's credentials with its own model id, not the primary."""
    config = models(
        writer={
            "model": "write-on-fallback",
            "temperature": 0.0,
            "max_output_tokens": 256,
            "pinned": True,
            "fallbacks": [],
            "gateway": "fallback",
        }
    )
    routes = client(setting=with_fallback_provider(), model_config=config).routes_for("writer")
    assert [(r.model, r.provider) for r in routes] == [("write-on-fallback", "fallback")]
    assert routes[0].base_url.rstrip("/") == FALLBACK


def test_a_pinned_agent_on_the_fallback_gateway_fails_clearly_if_unconfigured() -> None:
    config = models(
        writer={
            "model": "write-on-fallback",
            "temperature": 0.0,
            "max_output_tokens": 256,
            "pinned": True,
            "fallbacks": [],
            "gateway": "fallback",
        }
    )
    # Explicit None, not the default settings() — the real .env on disk may
    # itself have LLM_FALLBACK_URL/KEY set (pydantic-settings merges dotenv
    # even through model_validate), which would make this test's premise
    # false by accident of the local environment.
    unconfigured = settings(llm_fallback_url=None, llm_fallback_api_key=None)
    with pytest.raises(LlmConfigurationError, match="fallback gateway"):
        client(setting=unconfigured, model_config=config).routes_for("writer")


def test_a_pinned_agent_can_be_routed_through_the_secondary_gateway() -> None:
    """Fact-checker's real use case: a third, distinct vendor from both the
    primary gateway and Writer's fallback gateway."""
    config = models(
        fact_checker={
            "model": "check-on-secondary",
            "temperature": 0.0,
            "max_output_tokens": 256,
            "pinned": True,
            "fallbacks": [],
            "gateway": "secondary",
        }
    )
    routes = client(setting=with_secondary_provider(), model_config=config).routes_for(
        "fact_checker"
    )
    assert [(r.model, r.provider) for r in routes] == [("check-on-secondary", "secondary")]
    assert routes[0].base_url.rstrip("/") == SECONDARY


def test_a_pinned_agent_on_the_secondary_gateway_fails_clearly_if_unconfigured() -> None:
    config = models(
        fact_checker={
            "model": "check-on-secondary",
            "temperature": 0.0,
            "max_output_tokens": 256,
            "pinned": True,
            "fallbacks": [],
            "gateway": "secondary",
        }
    )
    unconfigured = settings(llm_secondary_url=None, llm_secondary_api_key=None)
    with pytest.raises(LlmConfigurationError, match="LLM_SECONDARY"):
        client(setting=unconfigured, model_config=config).routes_for("fact_checker")


def test_an_unpinned_agent_with_no_fallback_model_gets_no_fallback_route() -> None:
    config = models(
        image_finder={
            "model": "image-1",
            "temperature": 0.0,
            "max_output_tokens": 256,
            "pinned": False,
            "fallbacks": [],
            "fallback_model": None,
        }
    )
    routes = client(setting=with_fallback_provider(), model_config=config).routes_for(
        "image_finder"
    )
    assert [r.provider for r in routes] == ["primary"]


def test_a_placeholder_model_is_refused_before_any_call() -> None:
    config = models(
        ranker={
            "model": UNSET_MODEL,
            "temperature": 0.0,
            "max_output_tokens": 256,
            "pinned": False,
            "fallbacks": [],
        }
    )
    with pytest.raises(LlmConfigurationError, match="placeholder"):
        client(model_config=config).complete("ranker", PROMPT)


# ------------------------------------------------------------ retry, failover


@respx.mock
def test_a_transient_failure_is_retried_on_the_same_route() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json=completion("recovered")),
        ]
    )
    result = client().complete("ranker", PROMPT)

    assert result.text == "recovered"
    assert result.attempts == 2
    assert requested_models() == ["rank-1", "rank-1"]


@respx.mock
def test_an_unpinned_agent_fails_over_to_the_next_model() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(200, json=completion("second model")),
        ]
    )
    result = client().complete("ranker", PROMPT)

    assert result.text == "second model"
    assert result.model == "rank-2"
    assert requested_models() == ["rank-1", "rank-1", "rank-1", "rank-2"]


@respx.mock
def test_a_pinned_agent_never_fails_over_to_another_model() -> None:
    """A silent model swap would change published wording without an eval."""
    respx.post(f"{PRIMARY}/chat/completions").mock(return_value=httpx.Response(500))

    with pytest.raises(LlmUnavailableError):
        client(setting=with_fallback_provider()).complete("writer", PROMPT)

    assert set(requested_models()) == {"write-1"}
    assert all(call.request.url.host == "primary.llm" for call in respx.calls)


def _pinned_with_availability_fallback() -> ModelsConfig:
    return models(
        fact_checker={
            "model": "check-1",
            "temperature": 0.0,
            "max_output_tokens": 256,
            "pinned": True,
            "gateway": "secondary",
            "availability_fallback_model": "check-fb",
            "availability_fallback_gateway": "primary",
        }
    )


@respx.mock
def test_a_pinned_agent_falls_back_after_availability_errors_exhaust_the_primary() -> None:
    respx.post(f"{SECONDARY}/chat/completions").mock(return_value=httpx.Response(429))
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=httpx.Response(200, json=completion("rescued"))
    )
    result = client(
        setting=with_secondary_provider(), model_config=_pinned_with_availability_fallback()
    ).complete("fact_checker", PROMPT)

    assert result.text == "rescued"
    assert result.model == "check-fb"
    assert result.provider == "primary"


@respx.mock
def test_a_pinned_agent_does_not_fall_back_after_a_fatal_error() -> None:
    """A malformed request would likely fail on the fallback provider too —
    the escape hatch is for the primary being unavailable, not fatal."""
    respx.post(f"{SECONDARY}/chat/completions").mock(
        return_value=httpx.Response(400, json={"error": {"message": "bad request"}})
    )
    primary_route = respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=httpx.Response(200, json=completion("should not be reached"))
    )

    with pytest.raises(LlmUnavailableError):
        client(
            setting=with_secondary_provider(), model_config=_pinned_with_availability_fallback()
        ).complete("fact_checker", PROMPT)

    assert primary_route.call_count == 0


def test_routes_for_a_pinned_agent_with_availability_fallback_is_still_one_route() -> None:
    """The escape hatch never shows up in routes_for() — a healthy primary
    must behave exactly like a pinned agent with no fallback at all."""
    routes = client(
        setting=with_secondary_provider(), model_config=_pinned_with_availability_fallback()
    ).routes_for("fact_checker")
    assert [(r.model, r.provider) for r in routes] == [("check-1", "secondary")]


@respx.mock
def test_a_fatal_status_is_not_retried_on_the_same_route() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        side_effect=[
            httpx.Response(400, json={"error": {"message": "bad request"}}),
            httpx.Response(200, json=completion("next model")),
        ]
    )
    result = client().complete("ranker", PROMPT)

    assert result.model == "rank-2"
    assert requested_models() == ["rank-1", "rank-2"]


@respx.mock
def test_an_empty_completion_is_treated_as_a_failure() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        side_effect=[
            httpx.Response(200, json=completion("   ")),
            httpx.Response(200, json=completion("real content")),
        ]
    )
    result = client().complete("ranker", PROMPT)

    assert result.text == "real content"
    assert result.attempts == 2


# ---------------------------------------------------------------- the guard


def test_an_email_address_in_a_prompt_is_refused() -> None:
    prompt = [Message(role="user", content="Write to reader@example.com about this.")]
    with pytest.raises(PersonalDataInPromptError):
        client().complete("ranker", prompt)


def test_a_user_id_in_a_prompt_is_refused() -> None:
    prompt = [Message(role="user", content="User 3f2504e0-4f89-11d3-9a0c-0305e82c3301 liked this.")]
    with pytest.raises(PersonalDataInPromptError):
        client().complete("ranker", prompt)


def test_the_guard_message_does_not_echo_the_identifier() -> None:
    prompt = [Message(role="user", content="mail reader@example.com")]
    with pytest.raises(PersonalDataInPromptError) as caught:
        client().complete("ranker", prompt)
    assert "reader@example.com" not in str(caught.value)


# -------------------------------------------------------------------- logging


@respx.mock
def test_every_attempt_is_recorded_including_failures() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json=completion("ok")),
        ]
    )
    recorder = Recorder()
    client(recorder=recorder).complete("ranker", PROMPT, prompt_version="writer-v1")

    assert [entry["status"] for entry in recorder.entries] == ["error", "ok"]
    assert recorder.entries[1]["prompt_tokens"] == 11
    assert recorder.entries[1]["completion_tokens"] == 7
    assert all(entry["agent"] == "ranker" for entry in recorder.entries)
    assert all(entry["prompt_version"] == "writer-v1" for entry in recorder.entries)

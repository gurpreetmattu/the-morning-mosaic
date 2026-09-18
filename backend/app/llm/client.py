"""The single entry point for every LLM call in the project.

Routing rules, from CLAUDE.md:

- Writer and Fact-checker use pinned models. Their output is what gets
  published, so a silent failover to a different model would change published
  wording without an eval run. Pinned agents therefore get exactly one route.
- Every other agent may fail over, first through the models listed in
  `fallbacks`, then to the configured fallback provider. Their output is
  re-checked downstream, so a substitution is recoverable.

The configured gateway (`LLM_GATEWAY_URL`/`LLM_GATEWAY_API_KEY` — Groq as of
this writing, previously the local `freellmpool` aggregator, see
docs/BACKLOG.md) is an OpenAI-compatible endpoint, and this talks to that wire
format directly over httpx rather than through the `openai` SDK. The SDK is
built on httpx2, a parallel stack our test tooling cannot intercept, which
would leave the routing rules above untested.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

from app.config.loader import load_models
from app.config.schemas import UNSET_MODEL, AgentKey, ModelsConfig, ModelSpec
from app.config.settings import Settings, get_settings
from app.llm.errors import (
    EmptyCompletionError,
    LlmConfigurationError,
    LlmHttpError,
    LlmProtocolError,
    LlmUnavailableError,
)
from app.llm.guard import assert_free_of_personal_data

Role = Literal["system", "user", "assistant"]

# Transient conditions worth another attempt on the same route.
RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

BACKOFF_BASE_SECONDS = 0.5
BACKOFF_MAX_SECONDS = 8.0


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class Route:
    """One provider endpoint paired with one model id."""

    base_url: str
    api_key: str
    model: str
    provider: str


@dataclass(frozen=True)
class LlmResult:
    text: str
    model: str
    provider: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int
    attempts: int


class CallRecorder(Protocol):
    """Persists one attempt. Injected so the client needs no database."""

    def record(
        self,
        *,
        agent: str,
        model: str,
        provider: str,
        prompt_version: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        latency_ms: int,
        status: str,
        error: str | None,
    ) -> None: ...


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.TransportError | EmptyCompletionError | LlmProtocolError):
        return True
    if isinstance(exc, LlmHttpError):
        return exc.status_code in RETRYABLE_STATUS
    return False


@dataclass(frozen=True)
class _Completion:
    text: str
    prompt_tokens: int | None
    completion_tokens: int | None


class LlmClient:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        models: ModelsConfig | None = None,
        recorder: CallRecorder | None = None,
        sleep: Callable[[float], None] = time.sleep,
        http: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._models = models or load_models()
        self._recorder = recorder
        self._sleep = sleep
        self._http = http or httpx.Client(timeout=self._models.request_timeout_seconds)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> LlmClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ routes

    def _gateway_creds(
        self, which: Literal["primary", "fallback", "secondary"]
    ) -> tuple[str, str] | None:
        url: Any
        key: Any
        if which == "primary":
            url, key = self._settings.llm_gateway_url, self._settings.llm_gateway_api_key
        elif which == "fallback":
            url, key = self._settings.llm_fallback_url, self._settings.llm_fallback_api_key
        else:
            url, key = self._settings.llm_secondary_url, self._settings.llm_secondary_api_key
        # A blank (but present) env value resolves to SecretStr(""), not
        # None — check the actual value, not just whether the field is set,
        # same reasoning as verify_turnstile's identical check.
        key_value = key.get_secret_value() if key else None
        if url is None or not key_value:
            return None
        return str(url), key_value

    def routes_for(self, agent: AgentKey) -> list[Route]:
        spec = self._models.agents[agent]
        if not spec.is_configured:
            raise LlmConfigurationError(
                f"agent {agent!r} still points at the {UNSET_MODEL} placeholder; "
                "set a real model id in config/models.yaml"
            )

        own = self._gateway_creds(spec.gateway)
        if own is None:
            env_prefix = {"fallback": "LLM_FALLBACK", "secondary": "LLM_SECONDARY"}[spec.gateway]
            raise LlmConfigurationError(
                f"agent {agent!r} is configured to use the {spec.gateway} gateway, "
                f"but {env_prefix}_URL/{env_prefix}_API_KEY are not set"
            )
        own_url, own_key = own

        if spec.pinned:
            # Exactly one route, by design. No model and no provider failover.
            return [Route(own_url, own_key, spec.model, spec.gateway)]

        models = [spec.model, *spec.fallbacks]
        routes = [Route(own_url, own_key, model, spec.gateway) for model in models]

        # The other gateway is a different vendor with its own model names,
        # so it does not reuse `models` (that list is specific to this
        # agent's own gateway's catalog). Only route to it when the agent
        # names a model that actually exists there, and it is configured.
        if spec.fallback_model:
            other = self._gateway_creds("fallback")
            if other is not None:
                other_url, other_key = other
                routes.append(Route(other_url, other_key, spec.fallback_model, "fallback"))
        return routes

    # ------------------------------------------------------------------- calls

    def complete(
        self,
        agent: AgentKey,
        messages: Sequence[Message],
        *,
        json_object: bool = False,
        prompt_version: str | None = None,
    ) -> LlmResult:
        # Before anything leaves the process.
        assert_free_of_personal_data(message.content for message in messages)

        spec = self._models.agents[agent]
        routes = self.routes_for(agent)
        payload = [{"role": message.role, "content": message.content} for message in messages]

        result, last_error, attempts, exhausted_by_availability = self._try_routes(
            agent, spec, routes, payload, json_object, prompt_version
        )
        if result is not None:
            return result

        # A pinned agent's own routes_for() returns exactly one route, by
        # design — no model or provider failover. This is a deliberately
        # separate, narrower mechanism: an outage escape hatch, tried only
        # when the primary was unavailable (never for a fatal error like a
        # malformed request, which the fallback provider would likely fail
        # on too), and only when the agent explicitly configures one. It
        # does not weaken "exactly one route" as the normal case — a
        # healthy primary never reaches this at all.
        if exhausted_by_availability and spec.availability_fallback_model:
            gateway = spec.availability_fallback_gateway
            assert gateway is not None  # enforced together in ModelSpec
            creds = self._gateway_creds(gateway)
            if creds is not None:
                fallback_route = Route(
                    creds[0], creds[1], spec.availability_fallback_model, gateway
                )
                result, last_error, more_attempts, _ = self._try_routes(
                    agent, spec, [fallback_route], payload, json_object, prompt_version
                )
                attempts += more_attempts
                if result is not None:
                    return result

        raise LlmUnavailableError(
            f"agent {agent!r}: all route(s) failed after {attempts} attempt(s)"
        ) from last_error

    def _try_routes(
        self,
        agent: AgentKey,
        spec: ModelSpec,
        routes: list[Route],
        payload: list[dict[str, str]],
        json_object: bool,
        prompt_version: str | None,
    ) -> tuple[LlmResult | None, Exception | None, int, bool]:
        """Returns (result, last_error, attempts, last_error_was_availability)."""
        attempts = 0
        last_error: Exception | None = None

        for route in routes:
            for attempt, delay in self._attempts():
                attempts += 1
                started = time.monotonic()
                try:
                    completion = self._call(route, spec, payload, json_object)
                # Broad by design: _is_retryable classifies, and every failure
                # must be recorded before it is re-raised or routed past.
                except Exception as exc:
                    elapsed = int((time.monotonic() - started) * 1000)
                    self._record(
                        agent, route, prompt_version, None, None, elapsed, "error", repr(exc)
                    )
                    last_error = exc
                    if not _is_retryable(exc):
                        break  # fatal for this route; move to the next one
                    if attempt < self._models.max_attempts:
                        self._sleep(delay)
                    continue

                elapsed = int((time.monotonic() - started) * 1000)
                self._record(
                    agent,
                    route,
                    prompt_version,
                    completion.prompt_tokens,
                    completion.completion_tokens,
                    elapsed,
                    "ok",
                    None,
                )
                return (
                    LlmResult(
                        text=completion.text,
                        model=route.model,
                        provider=route.provider,
                        prompt_tokens=completion.prompt_tokens,
                        completion_tokens=completion.completion_tokens,
                        latency_ms=elapsed,
                        attempts=attempts,
                    ),
                    None,
                    attempts,
                    False,
                )

        return None, last_error, attempts, last_error is not None and _is_retryable(last_error)

    # --------------------------------------------------------------- internals

    def _attempts(self) -> Iterator[tuple[int, float]]:
        for attempt in range(1, self._models.max_attempts + 1):
            delay = min(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), BACKOFF_MAX_SECONDS)
            yield attempt, delay

    def _call(
        self,
        route: Route,
        spec: ModelSpec,
        payload: list[dict[str, str]],
        json_object: bool,
    ) -> _Completion:
        body: dict[str, Any] = {
            "model": route.model,
            "messages": payload,
            "temperature": spec.temperature,
            "max_tokens": spec.max_output_tokens,
        }
        if json_object:
            body["response_format"] = {"type": "json_object"}

        response = self._http.post(
            f"{route.base_url.rstrip('/')}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {route.api_key}"},
        )
        if response.status_code != httpx.codes.OK:
            raise LlmHttpError(response.status_code, response.text[:200])

        try:
            data = response.json()
            choices = data["choices"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LlmProtocolError(f"{route.model}: unexpected response shape") from exc

        if not choices:
            raise EmptyCompletionError(f"{route.model} returned no choices")
        content = choices[0].get("message", {}).get("content")
        if not content or not content.strip():
            raise EmptyCompletionError(f"{route.model} returned empty content")

        usage = data.get("usage") or {}
        return _Completion(
            text=content,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )

    def _record(
        self,
        agent: AgentKey,
        route: Route,
        prompt_version: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        latency_ms: int,
        status: str,
        error: str | None,
    ) -> None:
        if self._recorder is None:
            return
        self._recorder.record(
            agent=agent,
            model=route.model,
            provider=route.provider,
            prompt_version=prompt_version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            status=status,
            error=error,
        )

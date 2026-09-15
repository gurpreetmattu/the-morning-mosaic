"""The single entry point for every LLM call in the project.

Routing rules, from CLAUDE.md:

- Writer and Fact-checker use pinned models. Their output is what gets
  published, so a silent failover to a different model would change published
  wording without an eval run. Pinned agents therefore get exactly one route.
- Every other agent may fail over, first through the models listed in
  `fallbacks`, then to the configured fallback provider. Their output is
  re-checked downstream, so a substitution is recoverable.

LLMBuffet is an OpenAI-compatible gateway, and this talks to that wire format
directly over httpx rather than through the `openai` SDK. The SDK is built on
httpx2, a parallel stack our test tooling cannot intercept, which would leave
the routing rules above untested.
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

    def routes_for(self, agent: AgentKey) -> list[Route]:
        spec = self._models.agents[agent]
        if not spec.is_configured:
            raise LlmConfigurationError(
                f"agent {agent!r} still points at the {UNSET_MODEL} placeholder; "
                "set a real model id in config/models.yaml"
            )

        primary_url = str(self._settings.llmbuffet_url)
        primary_key = self._settings.llmbuffet_api_key.get_secret_value()

        if spec.pinned:
            # Exactly one route, by design. No model and no provider failover.
            return [Route(primary_url, primary_key, spec.model, "primary")]

        models = [spec.model, *spec.fallbacks]
        routes = [Route(primary_url, primary_key, model, "primary") for model in models]

        fallback_url = self._settings.llm_fallback_url
        fallback_key = self._settings.llm_fallback_api_key
        if fallback_url is not None and fallback_key is not None:
            routes += [
                Route(str(fallback_url), fallback_key.get_secret_value(), model, "fallback")
                for model in models
            ]
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
                return LlmResult(
                    text=completion.text,
                    model=route.model,
                    provider=route.provider,
                    prompt_tokens=completion.prompt_tokens,
                    completion_tokens=completion.completion_tokens,
                    latency_ms=elapsed,
                    attempts=attempts,
                )

        raise LlmUnavailableError(
            f"agent {agent!r}: all {len(routes)} route(s) failed after {attempts} attempt(s)"
        ) from last_error

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

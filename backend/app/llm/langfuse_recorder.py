"""Sends LLM call metadata to Langfuse, alongside the database recorder.

Only metadata is sent — agent, model, provider, prompt version, token
counts, latency, status, and (on failure) the error string. Never message
content: Writer/Fact-checker input is unpublished source text, and nothing
in CLAUDE.md says that is safe to hand to a third-party tracing service, so
this stays exactly as blind to content as `DatabaseCallRecorder` already is.

Tracing must never break a build over an outage in a service that only
exists to observe it, so every call into the Langfuse SDK is caught and
logged, never raised.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from langfuse import Langfuse

from app.config.settings import Settings, get_settings
from app.llm.client import CallRecorder
from app.llm.recorder import DatabaseCallRecorder

logger = logging.getLogger(__name__)


class LangfuseCallRecorder:
    """Records one Langfuse generation per LLM call attempt."""

    def __init__(self, client: Langfuse) -> None:
        self._client = client

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
    ) -> None:
        usage_details: dict[str, int] = {}
        if prompt_tokens is not None:
            usage_details["input"] = prompt_tokens
        if completion_tokens is not None:
            usage_details["output"] = completion_tokens

        try:
            generation = self._client.start_observation(
                name=agent,
                as_type="generation",
                model=model,
                metadata={"provider": provider, "prompt_version": prompt_version},
                usage_details=usage_details or None,
                level="ERROR" if status == "error" else "DEFAULT",
                status_message=error,
            )
            generation.end()
        except Exception:  # tracing must never break a build
            logger.warning("langfuse: failed to record a call for agent %r", agent, exc_info=True)


class BroadcastCallRecorder:
    """Fans one record() call out to several recorders, in order."""

    def __init__(self, recorders: Sequence[CallRecorder]) -> None:
        self._recorders = recorders

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
    ) -> None:
        for recorder in self._recorders:
            recorder.record(
                agent=agent,
                model=model,
                provider=provider,
                prompt_version=prompt_version,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                status=status,
                error=error,
            )


@dataclass
class RecorderBundle:
    """What a job actually wires into LlmClient, plus how to flush it.

    `flush` is a no-op when Langfuse isn't configured, so every call site
    can call it unconditionally in a `finally` block rather than branching.
    """

    recorder: CallRecorder
    flush: Callable[[], None] = field(default=lambda: None)


def build_langfuse_client(settings: Settings) -> Langfuse | None:
    """None when Langfuse isn't configured — tracing is optional everywhere."""
    public_key = settings.langfuse_public_key
    secret_key = settings.langfuse_secret_key
    if public_key is None or secret_key is None or settings.langfuse_host is None:
        return None
    public_value = public_key.get_secret_value()
    secret_value = secret_key.get_secret_value()
    if not public_value or not secret_value:
        return None
    return Langfuse(
        public_key=public_value,
        secret_key=secret_value,
        host=str(settings.langfuse_host),
    )


def build_call_recorder(
    pipeline_run_id: uuid.UUID | None,
    *,
    settings: Settings | None = None,
) -> RecorderBundle:
    """The recorder every job wires into its LlmClient.

    Always the database; Langfuse tracing joins it only when configured.
    """
    settings = settings or get_settings()
    database = DatabaseCallRecorder(pipeline_run_id=pipeline_run_id)

    client = build_langfuse_client(settings)
    if client is None:
        return RecorderBundle(recorder=database)

    langfuse_recorder = LangfuseCallRecorder(client)
    return RecorderBundle(
        recorder=BroadcastCallRecorder([database, langfuse_recorder]),
        flush=client.flush,
    )

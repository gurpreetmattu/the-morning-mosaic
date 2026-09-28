"""LangfuseCallRecorder, BroadcastCallRecorder, and build_call_recorder.

No real Langfuse call is made here — `FakeLangfuseClient` stands in for the
SDK's `Langfuse` object so these stay real unit tests, exercising the same
`.start_observation(...).end()` shape the real client offers. Wiring against
the real, provisioned account is a manual/integration check, not a unit test.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import AnyHttpUrl, SecretStr

from app.config.settings import Settings
from app.llm.langfuse_recorder import (
    BroadcastCallRecorder,
    LangfuseCallRecorder,
    build_call_recorder,
    build_langfuse_client,
)


def call_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "agent": "writer",
        "model": "test-model",
        "provider": "groq",
        "prompt_version": "writer_v1",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "latency_ms": 250,
        "status": "ok",
        "error": None,
    }
    base.update(overrides)
    return base


class FakeObservation:
    def __init__(self, **fields: object) -> None:
        self.fields = fields
        self.ended = False

    def end(self) -> None:
        self.ended = True


class FakeLangfuseClient:
    def __init__(self, *, raise_on_start: bool = False) -> None:
        self.observations: list[FakeObservation] = []
        self.flushed = False
        self._raise_on_start = raise_on_start

    def start_observation(self, **kwargs: object) -> FakeObservation:
        if self._raise_on_start:
            raise RuntimeError("simulated Langfuse outage")
        observation = FakeObservation(**kwargs)
        self.observations.append(observation)
        return observation

    def flush(self) -> None:
        self.flushed = True


class RecordingRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def settings_with_langfuse(**overrides: Any) -> Settings:
    fields: dict[str, object] = {
        "langfuse_public_key": SecretStr("pk-test"),
        "langfuse_secret_key": SecretStr("sk-test"),
        "langfuse_host": AnyHttpUrl("https://langfuse.example.test"),
    }
    fields.update(overrides)
    return Settings.model_construct(**fields)  # type: ignore[arg-type]


# ---------------------------------------------------------- LangfuseCallRecorder


def test_a_successful_call_becomes_one_ended_generation() -> None:
    client = FakeLangfuseClient()
    LangfuseCallRecorder(client).record(**call_kwargs())  # type: ignore[arg-type]

    assert len(client.observations) == 1
    observation = client.observations[0]
    assert observation.ended
    assert observation.fields["name"] == "writer"
    assert observation.fields["as_type"] == "generation"
    assert observation.fields["model"] == "test-model"
    assert observation.fields["usage_details"] == {"input": 100, "output": 50}
    assert observation.fields["level"] == "DEFAULT"


def test_a_failed_call_is_recorded_at_error_level_with_the_message() -> None:
    client = FakeLangfuseClient()
    LangfuseCallRecorder(client).record(
        **call_kwargs(status="error", error="timeout", prompt_tokens=None, completion_tokens=None)  # type: ignore[arg-type]
    )

    observation = client.observations[0]
    assert observation.fields["level"] == "ERROR"
    assert observation.fields["status_message"] == "timeout"
    assert observation.fields["usage_details"] is None


def test_message_content_is_never_sent() -> None:
    """The whole point: only metadata crosses to the tracing service."""
    client = FakeLangfuseClient()
    LangfuseCallRecorder(client).record(**call_kwargs())  # type: ignore[arg-type]

    observation = client.observations[0]
    assert "content" not in observation.fields
    assert "messages" not in observation.fields
    assert "input" not in observation.fields
    assert "output" not in observation.fields


def test_a_langfuse_outage_never_raises() -> None:
    """Tracing must never break a build over its own failure."""
    client = FakeLangfuseClient(raise_on_start=True)
    LangfuseCallRecorder(client).record(**call_kwargs())  # type: ignore[arg-type]
    # No exception means the test passed.


# ------------------------------------------------------------ BroadcastCallRecorder


def test_broadcast_forwards_the_same_call_to_every_recorder() -> None:
    first, second = RecordingRecorder(), RecordingRecorder()
    BroadcastCallRecorder([first, second]).record(**call_kwargs())  # type: ignore[arg-type]

    assert first.calls == [call_kwargs()]
    assert second.calls == [call_kwargs()]


def test_broadcast_with_no_recorders_does_nothing() -> None:
    BroadcastCallRecorder([]).record(**call_kwargs())  # type: ignore[arg-type]
    # No exception means the test passed.


# ------------------------------------------------------------- build_langfuse_client


def test_no_client_is_built_when_keys_are_missing() -> None:
    settings = settings_with_langfuse(langfuse_public_key=None)
    assert build_langfuse_client(settings) is None


def test_no_client_is_built_when_a_key_is_blank() -> None:
    settings = settings_with_langfuse(langfuse_secret_key=SecretStr(""))
    assert build_langfuse_client(settings) is None


def test_no_client_is_built_when_the_host_is_missing() -> None:
    settings = settings_with_langfuse(langfuse_host=None)
    assert build_langfuse_client(settings) is None


# --------------------------------------------------------------- build_call_recorder


def test_without_langfuse_configured_the_bundle_is_just_the_database_recorder() -> None:
    settings = settings_with_langfuse(langfuse_public_key=None)
    bundle = build_call_recorder(uuid.uuid4(), settings=settings)

    # DatabaseCallRecorder, not wrapped in a broadcaster with nothing to add.
    assert not isinstance(bundle.recorder, BroadcastCallRecorder)
    bundle.flush()  # the no-op default; must not raise


def test_with_langfuse_configured_both_recorders_receive_every_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither real recorder runs here — DatabaseCallRecorder's own behaviour
    is covered against a real database in test_llm_recorder.py; this test is
    only about build_call_recorder's wiring, so both are faked out to avoid
    touching the configured (real, remote) database at all."""
    import app.llm.langfuse_recorder as module

    fake_client = FakeLangfuseClient()
    fake_database = RecordingRecorder()
    monkeypatch.setattr(module, "build_langfuse_client", lambda settings: fake_client)
    monkeypatch.setattr(module, "DatabaseCallRecorder", lambda pipeline_run_id: fake_database)

    settings = settings_with_langfuse()
    bundle = build_call_recorder(uuid.uuid4(), settings=settings)

    assert isinstance(bundle.recorder, BroadcastCallRecorder)
    bundle.recorder.record(**call_kwargs())  # type: ignore[arg-type]
    assert len(fake_client.observations) == 1
    assert fake_database.calls == [call_kwargs()]

    bundle.flush()
    assert fake_client.flushed

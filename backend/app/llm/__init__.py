"""LLM access. Every model call in the project goes through LlmClient."""

from app.llm.client import CallRecorder, LlmClient, LlmResult, Message, Route
from app.llm.errors import (
    EmptyCompletionError,
    LlmConfigurationError,
    LlmError,
    LlmHttpError,
    LlmProtocolError,
    LlmUnavailableError,
    PersonalDataInPromptError,
)
from app.llm.guard import assert_free_of_personal_data, find_identifiers
from app.llm.langfuse_recorder import (
    BroadcastCallRecorder,
    LangfuseCallRecorder,
    RecorderBundle,
    build_call_recorder,
    build_langfuse_client,
)
from app.llm.recorder import DatabaseCallRecorder

__all__ = [
    "BroadcastCallRecorder",
    "CallRecorder",
    "DatabaseCallRecorder",
    "EmptyCompletionError",
    "LangfuseCallRecorder",
    "LlmClient",
    "LlmConfigurationError",
    "LlmError",
    "LlmHttpError",
    "LlmProtocolError",
    "LlmResult",
    "LlmUnavailableError",
    "Message",
    "PersonalDataInPromptError",
    "RecorderBundle",
    "Route",
    "assert_free_of_personal_data",
    "build_call_recorder",
    "build_langfuse_client",
    "find_identifiers",
]

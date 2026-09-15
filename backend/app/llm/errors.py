"""Failures the LLM client raises."""

from __future__ import annotations


class LlmError(Exception):
    """Base class for every LLM failure."""


class LlmConfigurationError(LlmError):
    """The configuration cannot be used, e.g. a placeholder model id."""


class PersonalDataInPromptError(LlmError):
    """A prompt contained something that identifies a subscriber.

    Raised before any network call. Nothing identifying a subscriber may
    reach a third-party model, so this is a hard failure rather than a
    redaction: silently stripping it would hide the bug that produced it.
    """


class LlmUnavailableError(LlmError):
    """Every route was tried and none produced a usable response."""


class LlmHttpError(LlmError):
    """A non-200 response from the gateway."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}{f': {detail}' if detail else ''}")


class LlmProtocolError(LlmError):
    """A 200 response that did not match the chat-completions shape."""


class EmptyCompletionError(LlmError):
    """The provider answered, but with no content. Treated as retryable."""

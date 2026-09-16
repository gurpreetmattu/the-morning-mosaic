"""Tokens and the SMTP sender. No mail leaves the process."""

from __future__ import annotations

import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.email import tokens
from app.email.sender import Message, Sender, SendError, SendOutcome
from app.email.tokens import TokenError
from app.models.enums import TokenPurpose
from app.models.users import Token

NOW = datetime(2026, 10, 5, 4, 0, tzinfo=UTC)


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "base_url": "https://mosaic.example.com",
        "database_url": "postgresql://u:p@localhost/db",
        "smtp_host": "smtp.example.com",
        "sender_email": "news@example.com",
        "sender_name": "The Morning Mosaic",
        "gmail_app_password": "x",
        "imap_host": "imap.example.com",
        "admin_email": "admin@example.com",
        "llmbuffet_url": "https://llm.example.com",
        "llmbuffet_api_key": "x",
        "token_signing_key": "signing-key-for-tests",
    }
    return Settings.model_validate(base | overrides)


@pytest.fixture(autouse=True)
def _signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tokens, "get_settings", settings)


# ---------------------------------------------------------- stateless tokens


def test_a_signed_token_round_trips() -> None:
    token = tokens.sign(tokens.FEEDBACK, "story-42", vote="up")
    claims = tokens.verify(token, tokens.FEEDBACK)

    assert claims.subject == "story-42"
    assert claims.extra["vote"] == "up"


def test_a_tampered_payload_is_rejected() -> None:
    token = tokens.sign(tokens.FEEDBACK, "story-42")
    body, signature = token.split(".", 1)
    forged = tokens.sign(tokens.FEEDBACK, "story-99").split(".", 1)[0]

    with pytest.raises(TokenError, match="bad signature"):
        tokens.verify(f"{forged}.{signature}", tokens.FEEDBACK)
    assert body != forged


def test_a_token_for_one_purpose_cannot_be_replayed_as_another() -> None:
    token = tokens.sign(tokens.FEEDBACK, "story-42")
    with pytest.raises(TokenError, match="wrong purpose"):
        tokens.verify(token, tokens.PDF)


def test_an_expired_token_is_rejected() -> None:
    token = tokens.sign(tokens.PDF, "rev-1", expires_in=timedelta(hours=1), now=NOW)

    assert tokens.verify(token, tokens.PDF, now=NOW + timedelta(minutes=59))
    with pytest.raises(TokenError, match="expired"):
        tokens.verify(token, tokens.PDF, now=NOW + timedelta(hours=2))


def test_a_token_without_an_expiry_does_not_expire() -> None:
    token = tokens.sign(tokens.FEEDBACK, "story-42", now=NOW)
    claims = tokens.verify(token, tokens.FEEDBACK, now=NOW + timedelta(days=3650))
    assert claims.expires_at is None


def test_malformed_tokens_are_rejected_not_crashed() -> None:
    for bad in ("", "nodot", "a.b", "...."):
        with pytest.raises(TokenError):
            tokens.verify(bad, tokens.FEEDBACK)


# -------------------------------------------------------------- the sender


class FakeSMTP:
    """Captures what would have been sent."""

    def __init__(self, fail: bool = False) -> None:
        self.sent: list[EmailMessage] = []
        self.quit_called = 0
        self.fail = fail

    def send_message(self, message: EmailMessage) -> None:
        if self.fail:
            raise smtplib.SMTPServerDisconnected("connection lost")
        self.sent.append(message)

    def quit(self) -> None:
        self.quit_called += 1


def sender(
    smtp: FakeSMTP | None = None, **setting_overrides: Any
) -> tuple[Sender, FakeSMTP, list[float]]:
    transport = smtp or FakeSMTP()
    slept: list[float] = []
    subject = Sender(
        settings=settings(**setting_overrides),
        transport=lambda: transport,  # type: ignore[arg-type,return-value]
        sleep=slept.append,
    )
    return subject, transport, slept


def message(**overrides: Any) -> Message:
    base: dict[str, Any] = {
        "to": "reader@example.com",
        "subject": "The Morning Mosaic — 5 October",
        "html": "<p>Good morning.</p>",
        "text": "Good morning.",
        "unsubscribe_url": "https://mosaic.example.com/u/abc",
    }
    return Message(**(base | overrides))


def test_prod_sends_to_any_recipient() -> None:
    subject, smtp, _ = sender(app_env="prod")
    result = subject.send(message())

    assert result.outcome is SendOutcome.SENT
    assert len(smtp.sent) == 1
    assert smtp.quit_called == 1


def test_dev_refuses_an_address_that_is_not_allowlisted() -> None:
    """The rule that keeps development from mailing real subscribers."""
    subject, smtp, _ = sender(app_env="dev", test_email_allowlist="me@example.com")
    result = subject.send(message(to="stranger@example.com"))

    assert result.outcome is SendOutcome.SUPPRESSED
    assert smtp.sent == []


def test_dev_with_an_empty_allowlist_sends_nothing_at_all() -> None:
    subject, smtp, _ = sender(app_env="dev")
    assert subject.send(message()).outcome is SendOutcome.SUPPRESSED
    assert smtp.sent == []


def test_dev_sends_to_an_allowlisted_address() -> None:
    subject, smtp, _ = sender(app_env="dev", test_email_allowlist="reader@example.com")
    assert subject.send(message()).outcome is SendOutcome.SENT
    assert len(smtp.sent) == 1


def test_the_message_is_multipart_with_text_before_html() -> None:
    subject, smtp, _ = sender(app_env="prod")
    subject.send(message())

    sent = smtp.sent[0]
    parts = [part.get_content_type() for part in sent.iter_parts()]
    # The last alternative wins in a mail client, so HTML must come second.
    assert parts == ["text/plain", "text/html"]


def test_one_click_unsubscribe_headers_are_present() -> None:
    subject, smtp, _ = sender(app_env="prod")
    subject.send(message())

    sent = smtp.sent[0]
    assert sent["List-Unsubscribe"] == "<https://mosaic.example.com/u/abc>"
    assert sent["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_there_is_no_way_to_bcc_a_second_recipient() -> None:
    subject, smtp, _ = sender(app_env="prod")
    subject.send(message())

    sent = smtp.sent[0]
    assert sent["To"] == "reader@example.com"
    assert sent["Bcc"] is None
    assert sent["Cc"] is None


def test_the_from_header_uses_the_configured_sender() -> None:
    subject, smtp, _ = sender(app_env="prod")
    subject.send(message())
    assert smtp.sent[0]["From"] == "The Morning Mosaic <news@example.com>"


def test_sends_are_throttled_after_the_first() -> None:
    subject, _, slept = sender(app_env="prod")
    subject.send(message())
    subject.send(message(to="other@example.com"))

    assert slept == [0.5]  # nothing before the first send


def test_a_suppressed_send_does_not_count_as_a_send() -> None:
    subject, _, slept = sender(app_env="dev", test_email_allowlist="me@example.com")
    subject.send(message(to="stranger@example.com"))
    subject.send(message(to="also-stranger@example.com"))
    assert slept == []


def test_an_smtp_failure_raises_for_the_caller_to_record() -> None:
    subject, _, _ = sender(FakeSMTP(fail=True), app_env="prod")
    with pytest.raises(SendError, match="SMTPServerDisconnected"):
        subject.send(message())


def test_a_message_without_an_unsubscribe_url_omits_the_headers() -> None:
    subject, smtp, _ = sender(app_env="prod")
    subject.send(message(unsubscribe_url=None))
    assert smtp.sent[0]["List-Unsubscribe"] is None


# ------------------------------------------------- stored tokens (database)


@pytest.mark.integration
def test_a_stored_token_is_kept_only_as_a_hash(session: Session) -> None:
    """A database leak must not hand anyone a working magic link."""
    raw = tokens.issue(session, user_id=None, purpose=TokenPurpose.MAGIC_LINK, now=NOW)
    stored = session.scalar(select(Token))

    assert stored is not None
    assert stored.token_hash != raw
    assert stored.token_hash == tokens.hash_token(raw)


@pytest.mark.integration
def test_a_magic_link_works_once(session: Session) -> None:
    raw = tokens.issue(session, user_id=None, purpose=TokenPurpose.MAGIC_LINK, now=NOW)

    assert tokens.redeem(session, raw, TokenPurpose.MAGIC_LINK, now=NOW) is not None
    with pytest.raises(TokenError, match="already used"):
        tokens.redeem(session, raw, TokenPurpose.MAGIC_LINK, now=NOW)


@pytest.mark.integration
def test_an_expired_magic_link_is_refused(session: Session) -> None:
    raw = tokens.issue(session, user_id=None, purpose=TokenPurpose.MAGIC_LINK, now=NOW)
    with pytest.raises(TokenError, match="expired"):
        tokens.redeem(session, raw, TokenPurpose.MAGIC_LINK, now=NOW + timedelta(hours=1))


@pytest.mark.integration
def test_an_unsubscribe_token_never_expires_and_can_be_used_twice(session: Session) -> None:
    """A link in a two-year-old email must still work, and twice is not an error."""
    raw = tokens.issue(session, user_id=None, purpose=TokenPurpose.UNSUBSCRIBE, now=NOW)
    far_future = NOW + timedelta(days=3650)

    assert tokens.redeem(session, raw, TokenPurpose.UNSUBSCRIBE, now=far_future)
    assert tokens.redeem(session, raw, TokenPurpose.UNSUBSCRIBE, now=far_future)


@pytest.mark.integration
def test_a_token_cannot_be_redeemed_for_a_different_purpose(session: Session) -> None:
    raw = tokens.issue(session, user_id=None, purpose=TokenPurpose.OPT_IN, now=NOW)
    with pytest.raises(TokenError, match="unknown token"):
        tokens.redeem(session, raw, TokenPurpose.MAGIC_LINK, now=NOW)


@pytest.mark.integration
def test_an_unknown_token_is_refused(session: Session) -> None:
    with pytest.raises(TokenError, match="unknown token"):
        tokens.redeem(session, "never-issued", TokenPurpose.MAGIC_LINK, now=NOW)

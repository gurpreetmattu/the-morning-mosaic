"""SMTP sending.

Three rules from CLAUDE.md are enforced here rather than at the call site,
because the call site is exactly where they get forgotten:

- **One email per recipient, never BCC.** The API takes a single address; there
  is no way to pass a list.
- **Dev never emails real subscribers.** Outside prod, every address is checked
  against TEST_EMAIL_ALLOWLIST and suppressed if absent. An empty allowlist in
  dev means nothing sends at all, which is the safe default.
- **One-click unsubscribe.** Every message carries `List-Unsubscribe` and
  `List-Unsubscribe-Post`, so mail clients show their own unsubscribe button
  and Gmail stops treating the mail as suspicious.

Gmail's quota covers all mail, transactional included, so sends are throttled
and the caller records the outcome.
"""

from __future__ import annotations

import logging
import smtplib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from enum import StrEnum

from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# A courtesy pause between sends so a batch does not arrive as a burst.
DEFAULT_THROTTLE_SECONDS = 0.5


class SendOutcome(StrEnum):
    SENT = "sent"
    # Refused before the SMTP call because dev may not mail this address.
    SUPPRESSED = "suppressed"


class SendError(Exception):
    """The SMTP conversation failed. The caller decides whether to retry."""


@dataclass
class Message:
    to: str
    subject: str
    html: str
    text: str
    # RFC 8058 one-click unsubscribe. Required on newsletters and notices.
    unsubscribe_url: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SendResult:
    to: str
    outcome: SendOutcome
    message_id: str | None = None
    reason: str | None = None


Transport = Callable[[], smtplib.SMTP]


def _default_transport() -> smtplib.SMTP:
    settings = get_settings()
    client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
    client.starttls()
    client.login(settings.sender_email, settings.gmail_app_password.get_secret_value())
    return client


class Sender:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: Transport = _default_transport,
        sleep: Callable[[float], None] = time.sleep,
        throttle_seconds: float = DEFAULT_THROTTLE_SECONDS,
    ) -> None:
        self._settings = settings or get_settings()
        self._transport = transport
        self._sleep = sleep
        self._throttle = throttle_seconds
        self._sent_any = False

    def build(self, message: Message) -> EmailMessage:
        settings = self._settings
        email = EmailMessage()
        email["Subject"] = message.subject
        email["From"] = formataddr((settings.sender_name, str(settings.sender_email)))
        email["To"] = message.to
        email["Message-ID"] = make_msgid()

        if message.unsubscribe_url:
            email["List-Unsubscribe"] = f"<{message.unsubscribe_url}>"
            # Tells the client it may POST rather than open the link, which is
            # what makes the native one-click button appear.
            email["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        for name, value in message.extra_headers.items():
            email[name] = value

        # Plain text first: the last part of an alternative is the preferred
        # one, so the HTML must come second.
        email.set_content(message.text)
        email.add_alternative(message.html, subtype="html")
        return email

    def send(self, message: Message) -> SendResult:
        if not self._settings.may_send_to(message.to):
            # Not an error: this is the dev guard doing its job.
            logger.info("suppressed outside prod", extra={"env": self._settings.app_env})
            return SendResult(
                to=message.to,
                outcome=SendOutcome.SUPPRESSED,
                reason="address is not on TEST_EMAIL_ALLOWLIST",
            )

        if self._sent_any and self._throttle:
            self._sleep(self._throttle)

        email = self.build(message)
        try:
            client = self._transport()
            try:
                client.send_message(email)
            finally:
                client.quit()
        except (smtplib.SMTPException, OSError) as exc:
            raise SendError(f"{type(exc).__name__}: {exc}") from exc

        self._sent_any = True
        return SendResult(to=message.to, outcome=SendOutcome.SENT, message_id=email["Message-ID"])

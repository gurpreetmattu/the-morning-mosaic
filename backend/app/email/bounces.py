"""Reading delivery failures out of the sender mailbox.

Gmail's SMTP accepts mail for an address that does not exist and reports the
failure later, as an ordinary email to the sender. So the only way to learn
that an address is dead is to read that mailbox.

The app password we hold grants full access to it, which is more authority
than this job needs, so the limits are structural rather than promised:

- the mailbox is opened **read-only**, which makes deleting, flagging and
  moving impossible at the protocol level, not merely unattempted;
- the IMAP search is narrowed to delivery-failure reports before anything is
  fetched, so ordinary mail is never pulled down, let alone parsed;
- nothing here can send.

Only a permanent failure (SMTP 5.x.x) marks an address. A full mailbox or a
temporary outage is 4.x.x and is ignored: dropping a reader over a transient
problem loses them for good.
"""

from __future__ import annotations

import contextlib
import imaplib
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from email import message_from_bytes
from email.message import Message
from typing import Protocol

logger = logging.getLogger(__name__)

# Per-recipient fields of a delivery status report (RFC 3464).
_FINAL_RECIPIENT = re.compile(r"^Final-Recipient:\s*rfc822;\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_STATUS = re.compile(r"^Status:\s*([245])\.\d+\.\d+", re.IGNORECASE | re.MULTILINE)
_ACTION = re.compile(r"^Action:\s*(\w+)", re.IGNORECASE | re.MULTILINE)
# Prose bounces put the code inline ("550 5.1.1 user unknown"), so the body
# scan cannot require it at the start of a line the way a report field is.
_LOOSE_STATUS = re.compile(r"\b([245])\.\d{1,3}\.\d{1,3}\b")

# Only these are fetched. Anything else in the mailbox is never read.
BOUNCE_SEARCH = '(FROM "mailer-daemon")'


@dataclass(frozen=True)
class Bounce:
    address: str
    permanent: bool
    status: str


def parse_bounce(message: Message) -> Bounce | None:
    """Extract the failed recipient, or None if this is not a bounce report."""
    report = _delivery_status(message)
    if report is None:
        return _from_failed_recipients_header(message)

    recipient = _FINAL_RECIPIENT.search(report)
    status = _STATUS.search(report)
    if recipient is None or status is None:
        return None

    action = _ACTION.search(report)
    if action is not None and action.group(1).lower() != "failed":
        # "delayed" is the mail system still trying; it is not a verdict.
        return None

    return Bounce(
        address=_clean(recipient.group(1)),
        permanent=status.group(1) == "5",
        status=status.group(0).split(":", 1)[1].strip(),
    )


def _delivery_status(message: Message) -> str | None:
    for part in message.walk():
        if part.get_content_type() == "message/delivery-status":
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes):
                return payload.decode("utf-8", errors="replace")
            return "\n\n".join(str(sub) for sub in part.get_payload())
    return None


def _from_failed_recipients_header(message: Message) -> Bounce | None:
    """Some MTAs report only in a header, with no structured report attached.

    Treated as permanent only when the body carries a 5.x.x code, so a
    transient failure is never mistaken for a dead address.
    """
    failed = message.get("X-Failed-Recipients")
    if not failed:
        return None

    status = _LOOSE_STATUS.search(_plain_text(message))
    return Bounce(
        address=_clean(failed.split(",")[0]),
        # Absent a code, assume transient: a wrongly kept address costs a
        # little quota, a wrongly dropped reader is gone for good.
        permanent=bool(status and status.group(1) == "5"),
        status=status.group(0) if status else "unknown",
    )


def _plain_text(message: Message) -> str:
    for part in message.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes):
                return payload.decode("utf-8", errors="replace")
    return ""


def _clean(address: str) -> str:
    return address.strip().strip("<>").strip().lower()


class BounceSource(Protocol):
    """Where bounce reports come from. Injected so tests need no mailbox."""

    def fetch(self, *, since: date) -> Iterator[Message]: ...


class ImapBounceSource:
    """Reads delivery failures over IMAP. Opens the mailbox read-only."""

    def __init__(
        self, *, host: str, port: int, username: str, password: str, mailbox: str = "INBOX"
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._mailbox = mailbox

    def fetch(self, *, since: date) -> Iterator[Message]:
        client = imaplib.IMAP4_SSL(self._host, self._port)
        try:
            client.login(self._username, self._password)
            # readonly=True: the session cannot delete, flag or move anything.
            client.select(self._mailbox, readonly=True)

            criteria = f'{BOUNCE_SEARCH} (SINCE "{since.strftime("%d-%b-%Y")}")'
            status, data = client.search(None, criteria)
            if status != "OK" or not data or not data[0]:
                return

            for number in data[0].split():
                fetch_status, payload = client.fetch(number, "(RFC822)")
                if fetch_status != "OK" or not payload:
                    continue
                for item in payload:
                    if isinstance(item, tuple) and isinstance(item[1], bytes):
                        yield message_from_bytes(item[1])
        finally:
            # close() fails if select() never succeeded; logout must still run.
            with contextlib.suppress(imaplib.IMAP4.error, OSError):
                client.close()
            client.logout()

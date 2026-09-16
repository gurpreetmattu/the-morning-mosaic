"""Keep subscriber data out of prompts.

CLAUDE.md: never send personal data (names, emails, cities, user IDs) to any
LLM. The architecture is the primary defence — there is no per-user LLM
generation, so prompts are built from article passages, never from user rows.
This module is the backstop for when that assumption is broken by a future
change.

What it can and cannot catch:

- Email addresses and UUIDs are unambiguous identifiers, matched reliably.
- Names and city names are NOT matched. "Mumbai" and "Sharma" appear
  constantly in legitimate Indian news copy, so a pattern match would either
  reject every real prompt or be trivially incomplete. Those are prevented
  structurally, by never passing user rows into prompt construction, and that
  boundary is what the tests around the Writer must protect.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.llm.errors import PersonalDataInPromptError

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def find_identifiers(text: str) -> list[str]:
    """Return the identifiers found, without echoing surrounding content."""
    return [*EMAIL_RE.findall(text), *UUID_RE.findall(text)]


def redact_identifiers(text: str) -> str:
    """Strip identifiers from text that came from a source, not from us.

    Article copy legitimately contains email addresses — reporter contact
    lines, press office addresses — and passing one through would trip the
    guard on a perfectly normal story. Source text is therefore redacted on
    its way into a prompt.

    This redacts only the prompt copy. Stored passages keep their original
    text, so the audit trail still matches what the publisher printed. The
    guard stays strict, as a backstop for a future change that wrongly routes
    a user row into a prompt.
    """
    return UUID_RE.sub("[id removed]", EMAIL_RE.sub("[email removed]", text))


def assert_free_of_personal_data(texts: Iterable[str]) -> None:
    for text in texts:
        found = find_identifiers(text)
        if found:
            # The kind and count are logged; the values themselves are not,
            # because logs must never carry subscriber identifiers either.
            raise PersonalDataInPromptError(
                f"prompt contains {len(found)} subscriber identifier(s); refusing to send"
            )

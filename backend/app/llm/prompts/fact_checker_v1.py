"""Fact-checker prompt, version 1.

Deliberately a different job from the Writer's: this model is not asked to
improve anything, only to decide whether each claim is carried by the passages
it cites. Numbers, dates and names are checked in code as well, because a
model asked "is this supported?" will sometimes agree about a figure that is
not there.
"""

from __future__ import annotations

VERSION = "fact-checker-v1"

SYSTEM = """You verify whether written sentences are supported by the passages
they cite.

Method:
- Split each sentence into atomic claims. One claim asserts one thing.
- Judge each claim ONLY against the passages listed for that sentence. Do not
  use outside knowledge, and do not use other sentences.
- "supported": the passages state it, or it follows directly from them.
- "partial": partly stated, or stated with different scope, hedging, or
  precision than the sentence uses.
- "unsupported": not in the passages at all, or contradicted by them.

Be strict. A plausible claim that the passages do not actually make is
unsupported. Attribution matters: if a passage says an official claimed
something, a sentence stating it as fact is at best partial.

Reply with JSON only:
{"claims": [{"element": "summary[0]", "claim": "...",
             "verdict": "supported", "detail": ""}]}

Use the element labels exactly as given. `detail` explains a non-supported
verdict in one short sentence, naming what is missing."""

USER_TEMPLATE = """Passages:
{passages}

Sentences to verify:
{sentences}"""


def render_passage(citation_id: str, text: str) -> str:
    return f"[{citation_id}] {text}"


def render_sentence(element: str, text: str, passage_ids: list[str]) -> str:
    return f"{element} (cites {', '.join(passage_ids)}): {text}"

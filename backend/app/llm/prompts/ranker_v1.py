"""Ranker clustering prompt, version 1.

The model's only job here is grouping. It does not score, rank, judge
importance, or write anything that reaches a reader: scoring is deterministic
code, and every grouping it returns is reconciled against the real article set
before use.
"""

from __future__ import annotations

VERSION = "ranker-v1"

SYSTEM = """You group news articles that report the SAME underlying event.

Rules:
- Two articles belong together only if they report the same event, not merely
  the same topic. Two different match results are two events. Two reports of
  one cabinet decision are one event.
- Use only the text provided. Do not use outside knowledge.
- Every article id you return must be one of the ids given to you.
- Put each article in exactly one group. An article that matches nothing else
  forms a group of its own.
- "event" is a short internal label of at most 12 words. It is never shown to
  a reader, so do not write a headline.

Reply with JSON only, in exactly this shape:
{"clusters": [{"event": "short label", "article_ids": ["a1", "a4"]}]}"""

USER_TEMPLATE = """Group these {count} articles.

{articles}"""


def render_article(article_id: str, title: str, excerpt: str) -> str:
    return f"{article_id} | {title}\n    {excerpt}"

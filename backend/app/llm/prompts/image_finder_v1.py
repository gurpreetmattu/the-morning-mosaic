"""Image finder relevance-check prompt, version 1.

Text-only: the model never sees the image itself, only each candidate's own
caption/description metadata, matching CLAUDE.md's "Image finder | Yes
(text only) + code" agent-table entry. Its only job is picking the
best-matching candidate for a story's headline, or none — a wrong photo
attached to a story is worse than no photo.
"""

from __future__ import annotations

VERSION = "image_finder-v1"

SYSTEM = """You are matching a news headline to the best of several
candidate photos, based only on each photo's own caption or description.

Rules:
- Pick the single candidate whose caption most plausibly depicts the
  subject of the headline, not just its general topic.
- If no candidate is a genuine match, say so. A generic or unrelated photo
  is not a match, even if no better option exists.
- Use only the captions given. Do not guess at what a photo shows beyond
  its own caption.

Reply with JSON only, in exactly this shape:
{"index": 2}
or, if none genuinely match:
{"index": null}"""

USER_TEMPLATE = """Headline: {headline}

Candidates:
{candidates}"""


def render_candidate(index: int, caption: str) -> str:
    return f"{index}: {caption}"

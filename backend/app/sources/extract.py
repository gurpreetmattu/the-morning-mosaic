"""Full-text extraction and passage splitting.

The Writer never sees raw HTML. It sees numbered passages, and every sentence
it writes must cite the passage ids that support it, so passage numbering is
part of the audit trail rather than a formatting detail.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import trafilatura
from trafilatura.metadata import extract_metadata

from app.sources.schemas import Passage

# Below this, an extraction is a navigation stub, a consent wall, or a paywall
# teaser rather than an article. We do not try to detect paywalls precisely;
# the length floor is an honest proxy, and dropping a real short article is
# cheaper than publishing from a teaser.
MIN_ARTICLE_CHARS = 500

# Short fragments are headings, bylines, and captions, not claims to cite.
MIN_PASSAGE_CHARS = 60

# \xa0 is deliberate: news HTML is full of &nbsp;, and leaving those in would
# make otherwise-identical syndicated copy hash differently.
_WHITESPACE = re.compile(r"[ \t\xa0]+")
_BLANK_LINES = re.compile(r"\n{2,}")


@dataclass(frozen=True)
class Extraction:
    text: str
    passages: list[Passage]
    content_hash: str
    title: str | None
    author: str | None
    canonical_url: str | None


def normalise(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def content_hash(text: str) -> str:
    """Hash of normalised text, used to spot the same story syndicated twice."""
    collapsed = " ".join(normalise(text).lower().split())
    return hashlib.sha256(collapsed.encode("utf-8")).hexdigest()


def split_passages(text: str, *, min_chars: int = MIN_PASSAGE_CHARS) -> list[Passage]:
    """Split extracted text into numbered, citable passages."""
    passages: list[Passage] = []
    for block in _BLANK_LINES.split(text):
        for line in block.split("\n"):
            candidate = normalise(line)
            if len(candidate) < min_chars:
                continue
            passages.append(Passage(ordinal=len(passages) + 1, text=candidate))
    return passages


def extract_article(html: str, url: str | None = None) -> Extraction | None:
    """Extract an article, or None if nothing usable came out.

    favor_precision drops boilerplate aggressively: a false passage is far
    more expensive than a missing one, because the Writer may cite it.
    """
    text = trafilatura.extract(
        html,
        url=url,
        favor_precision=True,
        include_comments=False,
        include_tables=False,
        output_format="txt",
    )
    if not text or len(normalise(text)) < MIN_ARTICLE_CHARS:
        return None

    passages = split_passages(text)
    if not passages:
        return None

    title = author = canonical = None
    metadata = extract_metadata(html, default_url=url)
    if metadata is not None:
        title = metadata.title or None
        author = metadata.author or None
        canonical = metadata.url or None

    return Extraction(
        text=text,
        passages=passages,
        content_hash=content_hash(text),
        title=title,
        author=author,
        canonical_url=canonical,
    )

"""Deterministic checks on Writer output. No LLM.

CLAUDE.md requires the Writer to work strictly from supplied passages, cite
every sentence, use original wording, and stay within a fixed tag taxonomy.
None of that can be left to the prompt, so it is all checked here:

- every cited passage id must exist in this story's own passages;
- a sentence sharing a long run of words with a passage is copying, not
  rephrasing, unless it is a short attributed quote;
- topic tags outside the genre's taxonomy are removed;
- entity tags that do not appear in the passages are removed;
- india_relevance is computed from the passages and never read from the model;
- a tier-3-only story must actually contain hedging language.

Fatal problems drop the story. Everything else drops only the element, per
"if only an optional element fails ... drop just that element".
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache

from app.agents.checking import looks_like_a_proper_noun
from app.agents.schemas import (
    DraftSentence,
    PassageRef,
    WriterIssue,
    WriterProblem,
    WriterResult,
    WrittenStory,
)
from app.config.loader import load_cities
from app.sources.schemas import CollectedArticle

# A run of this many identical words is reproduction, not rephrasing.
MAX_VERBATIM_WORDS = 12
# CLAUDE.md allows "a short attributed quoted phrase". Fifteen words is a
# phrase; a typical news sentence runs past twenty, so quoting one whole is
# still caught even inside quotation marks.
MAX_QUOTED_WORDS = 15

_WORDS = re.compile(r"[a-z0-9']+")
_QUOTED = re.compile(r"[\"“]([^\"”]{2,})[\"”]")

# Language that marks a claim as reported rather than established.
HEDGE_MARKERS = (
    "reportedly",
    "according to",
    "said to",
    "is believed",
    "are believed",
    "claimed",
    "claims",
    "alleged",
    "rumoured",
    "rumored",
    "reports suggest",
    "sources said",
)

# India markers that are not place names.
_INDIA_TERMS = (
    "india",
    "indian",
    "indians",
    "rupee",
    "rupees",
    "lok sabha",
    "rajya sabha",
    "reserve bank of india",
    "supreme court of india",
    "isro",
    "sebi",
    "bcci",
    "niti aayog",
)


def _words(text: str) -> list[str]:
    return _WORDS.findall(text.lower())


@lru_cache(maxsize=1)
def india_markers() -> tuple[str, ...]:
    """Place names from config/cities.yaml plus fixed India-specific terms."""
    cities = load_cities().cities
    names = {city.name.lower() for city in cities} | {city.state.lower() for city in cities}
    return tuple(sorted(names | set(_INDIA_TERMS)))


def mentions_india(texts: Iterable[str]) -> bool:
    """Conservative: only counts places and terms we can name.

    A story about an Indian person or company not on the list reads as not
    India-relevant. Under-flagging only weakens ranking for readers who chose
    the India edition; over-flagging would put foreign stories in front of
    them, so erring this way is the cheaper mistake.
    """
    markers = india_markers()
    haystack = " ".join(texts).lower()
    return any(re.search(rf"\b{re.escape(marker)}\b", haystack) for marker in markers)


def has_hedge(texts: Iterable[str]) -> bool:
    haystack = " ".join(texts).lower()
    return any(marker in haystack for marker in HEDGE_MARKERS)


def longest_shared_run(sentence: str, passage_texts: Sequence[str]) -> int:
    """Longest run of consecutive words shared with any single passage."""
    left = _words(sentence)
    if not left:
        return 0

    best = 0
    for passage in passage_texts:
        right = _words(passage)
        if not right:
            continue
        previous = [0] * (len(right) + 1)
        for i in range(1, len(left) + 1):
            current = [0] * (len(right) + 1)
            for j in range(1, len(right) + 1):
                if left[i - 1] == right[j - 1]:
                    current[j] = previous[j - 1] + 1
                    best = max(best, current[j])
            previous = current
    return best


def copying_violation(sentence: str, passage_texts: Sequence[str]) -> str | None:
    """None if the sentence is acceptable, else a description of the problem."""
    overall = longest_shared_run(sentence, passage_texts)
    quoted_spans = _QUOTED.findall(sentence)
    quoted = max(
        (longest_shared_run(span, passage_texts) for span in quoted_spans),
        default=0,
    )

    if quoted > MAX_QUOTED_WORDS:
        return f"quoted passage of {quoted} words exceeds {MAX_QUOTED_WORDS}"
    if overall > MAX_VERBATIM_WORDS and overall > quoted:
        return f"{overall} consecutive words copied from a source passage"
    return None


def build_passages(articles: Sequence[CollectedArticle]) -> dict[str, PassageRef]:
    """Address every passage in a cluster as "a<article>:p<passage>"."""
    refs: dict[str, PassageRef] = {}
    for article_index, article in enumerate(articles, start=1):
        for passage in article.passages:
            citation_id = f"a{article_index}:{passage.citation_id}"
            refs[citation_id] = PassageRef(
                citation_id=citation_id,
                article_index=article_index,
                source_key=article.source_key,
                url=article.url,
                text=passage.text,
            )
    return refs


def _read_sentence(
    raw: object,
    passages: Mapping[str, PassageRef],
    problems: list[WriterProblem],
    *,
    label: str,
) -> DraftSentence | None:
    if isinstance(raw, str):
        text, cited = raw, []
    elif isinstance(raw, dict):
        text = str(raw.get("text", "")).strip()
        cited = [str(pid) for pid in raw.get("passage_ids", []) or []]
    else:
        problems.append(
            WriterProblem(issue=WriterIssue.UNPARSEABLE, detail=f"{label}: not a sentence")
        )
        return None

    if not text:
        problems.append(WriterProblem(issue=WriterIssue.UNPARSEABLE, detail=f"{label}: empty text"))
        return None

    if not cited:
        problems.append(
            WriterProblem(issue=WriterIssue.MISSING_CITATION, detail=f"{label}: no passage cited")
        )
        return None

    unknown = [pid for pid in cited if pid not in passages]
    if unknown:
        problems.append(
            WriterProblem(
                issue=WriterIssue.UNKNOWN_CITATION,
                detail=f"{label}: cites {unknown} which is not in this story",
            )
        )
        return None

    copied = copying_violation(text, [passages[pid].text for pid in cited])
    if copied is not None:
        problems.append(WriterProblem(issue=WriterIssue.COPIED_TEXT, detail=f"{label}: {copied}"))
        return None

    return DraftSentence(text=text, passage_ids=cited)


def validate_draft(
    payload: object,
    *,
    passages: Mapping[str, PassageRef],
    allowed_topic_tags: frozenset[str],
    require_hedge: bool,
    model: str | None = None,
    prompt_version: str | None = None,
) -> WriterResult:
    problems: list[WriterProblem] = []

    if not isinstance(payload, dict):
        return WriterResult(
            problems=[WriterProblem(issue=WriterIssue.UNPARSEABLE, detail="not a JSON object")]
        )

    headline = _read_sentence(payload.get("headline"), passages, problems, label="headline")
    if headline is None:
        problems.append(
            WriterProblem(issue=WriterIssue.EMPTY_HEADLINE, detail="headline is unusable")
        )
        return WriterResult(problems=problems)

    raw_summary = payload.get("summary") or []
    if not isinstance(raw_summary, list):
        raw_summary = [raw_summary]
    summary = [
        sentence
        for index, raw in enumerate(raw_summary)
        if (sentence := _read_sentence(raw, passages, problems, label=f"summary[{index}]"))
    ]
    if not summary:
        problems.append(
            WriterProblem(issue=WriterIssue.EMPTY_SUMMARY, detail="no usable summary sentence")
        )
        return WriterResult(problems=problems)

    # Optional elements: dropped rather than allowed to fail the story.
    one_liner = None
    if payload.get("one_liner") is not None:
        one_liner = _read_sentence(payload.get("one_liner"), passages, problems, label="one_liner")
        if one_liner is None:
            problems.append(
                WriterProblem(
                    issue=WriterIssue.DROPPED_ONE_LINER, detail="one-liner failed validation"
                )
            )

    why: list[DraftSentence] = []
    raw_why = payload.get("why_this_matters") or []
    if isinstance(raw_why, list):
        for index, raw in enumerate(raw_why):
            sentence = _read_sentence(raw, passages, problems, label=f"why_this_matters[{index}]")
            if sentence is None:
                why = []
                problems.append(
                    WriterProblem(
                        issue=WriterIssue.DROPPED_WHY_THIS_MATTERS,
                        detail="'why this matters' failed validation",
                    )
                )
                break
            why.append(sentence)

    topic_tags: list[str] = []
    for tag in payload.get("topic_tags") or []:
        candidate = str(tag).strip().lower()
        if candidate in allowed_topic_tags:
            topic_tags.append(candidate)
        else:
            problems.append(
                WriterProblem(
                    issue=WriterIssue.DROPPED_TOPIC_TAG,
                    detail=f"{candidate!r} is not in this genre's taxonomy",
                )
            )

    passage_texts = [ref.text for ref in passages.values()]
    entity_tags: list[str] = []
    for tag in payload.get("entity_tags") or []:
        candidate = str(tag).strip()
        if not candidate:
            continue
        grounded = re.search(rf"\b{re.escape(candidate)}\b", " ".join(passage_texts), re.IGNORECASE)
        if grounded and looks_like_a_proper_noun(candidate):
            entity_tags.append(candidate)
        elif not grounded:
            problems.append(
                WriterProblem(
                    issue=WriterIssue.DROPPED_ENTITY_TAG,
                    detail=f"{candidate!r} does not appear in the source passages",
                )
            )
        else:
            problems.append(
                WriterProblem(
                    issue=WriterIssue.DROPPED_ENTITY_TAG,
                    detail=f"{candidate!r} is a generic phrase, not a proper noun",
                )
            )

    published_text = [headline.text, *(s.text for s in summary)]
    if require_hedge and not has_hedge(published_text):
        problems.append(
            WriterProblem(
                issue=WriterIssue.MISSING_HEDGE,
                detail="tier-3-only story does not use hedged language",
            )
        )
        return WriterResult(problems=problems)

    story = WrittenStory(
        headline=headline,
        summary=summary,
        one_liner=one_liner,
        why_this_matters=why,
        topic_tags=topic_tags,
        entity_tags=entity_tags,
        india_relevance=mentions_india(passage_texts),
        hedged=require_hedge,
        model=model,
        prompt_version=prompt_version,
    )
    return WriterResult(story=story, problems=problems)

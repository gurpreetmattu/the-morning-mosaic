"""Deterministic verification of written sentences. No LLM.

CLAUDE.md: "Numbers, dates, and names are ALSO checked deterministically in
code." A model asked whether a figure is supported will sometimes say yes
about a figure it invented, so these checks do not ask — they compare the
written sentence against the exact passages it cited.

Every check is one-directional: everything asserted in the sentence must be
present in a cited passage. A passage may contain more than the sentence uses.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from app.agents.schemas import DraftSentence, WrittenStory

# --------------------------------------------------------------------- numbers

_DIGITS = re.compile(r"\d[\d,]*(?:\.\d+)?")

_UNITS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
# Indian scales matter here: "2,000 crore" is ordinary business copy.
_SCALES = {
    "thousand": 1_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "million": 1_000_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
    "billion": 1_000_000_000,
    "trillion": 1_000_000_000_000,
}
_NUMBER_WORDS = set(_UNITS) | set(_SCALES) | {"hundred", "and"}


def _digit_numbers(text: str) -> set[Decimal]:
    found: set[Decimal] = set()
    for match in _DIGITS.findall(text):
        try:
            found.add(Decimal(match.replace(",", "")))
        except InvalidOperation:  # pragma: no cover - defensive
            continue
    return found


def _spelled_numbers(text: str) -> set[Decimal]:
    """Evaluate runs of number words, so "nine hundred" matches 900."""
    found: set[Decimal] = set()
    run: list[str] = []

    def flush() -> None:
        words = [w for w in run if w != "and"]
        if not words:
            return
        total = current = 0
        for word in words:
            if word in _UNITS:
                current += _UNITS[word]
            elif word == "hundred":
                current = max(current, 1) * 100
            elif word in _SCALES:
                total += max(current, 1) * _SCALES[word]
                current = 0
        total += current
        if total:
            found.add(Decimal(total))

    for word in re.findall(r"[a-z]+", text.lower()):
        if word in _NUMBER_WORDS:
            run.append(word)
        else:
            flush()
            run = []
    flush()
    return found


def numbers_in(text: str) -> set[Decimal]:
    return _digit_numbers(text) | _spelled_numbers(text)


# ----------------------------------------------------------------------- dates

_MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_DATE_WORDS = tuple(_MONTHS) + tuple(_WEEKDAYS) + ("yesterday", "today", "tomorrow")


def dates_in(text: str) -> set[str]:
    lowered = text.lower()
    return {word for word in _DATE_WORDS if re.search(rf"\b{word}\b", lowered)}


# ----------------------------------------------------------------------- names

# Capitalised words that start sentences or are ordinary vocabulary.
_NOT_NAMES = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "if",
        "then",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "he",
        "she",
        "they",
        "we",
        "you",
        "i",
        "in",
        "on",
        "at",
        "by",
        "for",
        "from",
        "to",
        "with",
        "as",
        "of",
        "over",
        "under",
        "after",
        "before",
        "during",
        "said",
        "says",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "can",
        "not",
        "no",
        "yes",
        "new",
        "more",
        "most",
        "less",
        "least",
        "first",
        "second",
        "third",
        "last",
        "next",
        "many",
        "few",
        "several",
        "some",
        "all",
        "both",
        "each",
        "other",
        "another",
        "such",
        "than",
        "when",
        "where",
        "while",
        "who",
        "whom",
        "whose",
        "which",
        "what",
        "why",
        "how",
        "there",
        "here",
        "about",
        "into",
        "out",
        "up",
        "down",
        "off",
        "again",
        "further",
        "once",
    ]
)
# Lowercase connectors are kept inside a name so "Reserve Bank of India" stays
# one phrase. Splitting it would let an invented "Bank of England" pass
# whenever "Bank" and "England" each appear somewhere in the passages.
_CONNECTORS = "of|for|and|the|de|da|van|von|al|bin"
_WORD_PART = r"[A-Z][\w&'.-]*"
_CAPITALISED = re.compile(
    rf"\b{_WORD_PART}(?:\s+(?:{_CONNECTORS})\s+{_WORD_PART}|\s+{_WORD_PART})*"
)


def looks_like_a_proper_noun(candidate: str) -> bool:
    """Whether every significant word is capitalised, the shape a real
    entity tag should have.

    Used to reject a generic noun phrase an entity tag check would
    otherwise accept just because it happens to appear in the passages —
    "central bank" or "two Mumbai brokerages" alongside "Reserve Bank of
    India".
    """
    return _CAPITALISED.fullmatch(candidate.strip()) is not None

# Below the four-character floor a candidate is normally skipped, since
# raising the floor for every short capitalised word would flood the check
# with false positives ("Fed", "PM", ordinary words at a sentence's start).
# These are checked anyway: a made-up "SBI" or "IMF" is exactly the kind of
# invented entity the check exists to catch, and each is common enough
# in India-first news to be worth naming rather than raising the floor.
_KNOWN_SHORT_ACRONYMS = frozenset(
    {
        "RBI",
        "SBI",
        "IMF",
        "WHO",
        "GST",
        "ISRO",
        "DRDO",
        "BJP",
        "AAP",
        "BCCI",
        "ICC",
        "NASA",
        "FBI",
        "CIA",
        "NATO",
        "WTO",
        "IPL",
        "SEBI",
        "TRAI",
        "CBI",
        "NIA",
        "NDA",
        "UPA",
        "GDP",
        "CPI",
        "RTI",
        "PIL",
        "ISI",
        "G20",
        "IPO",
        "NPA",
        "PSU",
        "OTT",
        "MSME",
        "FDI",
        "FPI",
        "NRI",
        "UPI",
        "KYC",
        "PAN",
        "EPFO",
        "LIC",
        "ONGC",
        "NTPC",
        "CAG",
    }
)


def names_in(text: str) -> set[str]:
    """Proper-noun candidates, excluding the sentence's opening word.

    Deliberately conservative about what counts as a name: a missed name is
    checked by the model instead, while a false one would reject sound copy.
    """
    candidates: set[str] = set()
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        if not sentence:
            continue
        for match in _CAPITALISED.finditer(sentence):
            phrase = match.group(0).strip(" .,;:")
            if match.start() == 0 and phrase not in _KNOWN_SHORT_ACRONYMS:
                # Drop the leading word; keep the rest if it is still a name.
                # A known acronym is kept as-is even alone at the start of a
                # sentence ("RBI raised rates...") — it is never an ordinary
                # sentence-opening word like "The".
                parts = phrase.split(None, 1)
                if len(parts) < 2:
                    continue
                phrase = parts[1]
            too_short = len(phrase) < 4 and phrase not in _KNOWN_SHORT_ACRONYMS
            # A Title-Case headline capitalises every word by convention, so
            # the connector-joining above can merge the *whole headline*
            # into one "name" once the leading word is dropped ("Ministry
            # of Railways Clears High Speed Rail Corridor" -> "of Railways
            # Clears High Speed Rail Corridor") — a real entity name is
            # essentially never this long. Found live: this exact headline
            # shape false-flagged in a real groundedness eval run.
            too_long = len(phrase.split()) > 5
            if too_short or too_long or phrase.lower() in _NOT_NAMES:
                continue
            candidates.add(phrase)
    return candidates


# ------------------------------------------------------------------- the check


def unsupported_facts(
    sentence: str, cited_passages: Sequence[str], *, check_names: bool = True
) -> list[str]:
    """Everything asserted in the sentence that no cited passage supports.

    `check_names=False` for the headline: it is written in Title Case by
    convention, so nearly every word is capitalised regardless of whether
    it is part of a real proper noun — a pattern no length cap on the
    connector-joining regex reliably tells apart from a run of genuine
    names (found live: multiple distinct real headlines false-flagged this
    way even after capping candidate length). The model check on the same
    element remains the safety net, per this module's own stated tradeoff:
    "a missed name is checked by the model instead, while a false one
    would reject sound copy."
    """
    haystack = " ".join(cited_passages)
    problems: list[str] = []

    passage_numbers = numbers_in(haystack)
    for value in sorted(numbers_in(sentence) - passage_numbers):
        problems.append(f"the figure {value} does not appear in the cited passages")

    passage_dates = dates_in(haystack)
    for token in sorted(dates_in(sentence) - passage_dates):
        problems.append(f"the date reference {token!r} does not appear in the cited passages")

    if not check_names:
        return problems

    lowered = haystack.lower()
    for name in sorted(names_in(sentence)):
        if name.lower() in lowered:
            continue
        # A hyphenated join ("Mumbai-Ahmedabad corridor") is a common
        # headline convention for a passage that writes it as prose
        # ("...between Mumbai and Ahmedabad...") — not an invented entity,
        # as long as every half is itself grounded. Found live: this exact
        # shape false-flagged in a real groundedness eval run.
        halves = [half for half in name.split("-") if half]
        if len(halves) > 1 and all(half.lower() in lowered for half in halves):
            continue
        problems.append(f"the name {name!r} does not appear in the cited passages")

    return problems


def story_elements(story: WrittenStory) -> list[tuple[str, DraftSentence]]:
    """Every published sentence, labelled so a failure can name it."""
    elements: list[tuple[str, DraftSentence]] = [("headline", story.headline)]
    elements += [(f"summary[{i}]", s) for i, s in enumerate(story.summary)]
    if story.one_liner is not None:
        elements.append(("one_liner", story.one_liner))
    elements += [(f"why_this_matters[{i}]", s) for i, s in enumerate(story.why_this_matters)]
    return elements


def is_optional(element: str) -> bool:
    """Optional elements are dropped alone; the rest drop the story."""
    return element == "one_liner" or element.startswith("why_this_matters")

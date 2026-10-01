"""Corroboration and scoring — deterministic, no LLM.

Scoring deliberately uses only three signals: how many independent sources
carried the story, the best source tier, and how recent it is. None of them
can encode which side a story favours, which is how CLAUDE.md's political
balance rule ("ranking must not favor a story because of which side it
favors") is satisfied by construction rather than by instruction.

Clustering is proposed by a model, but every grouping it returns is reconciled
against the real article set here before it is used.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime

from app.agents.checking import numbers_in
from app.agents.schemas import Corroboration
from app.sources.schemas import CollectedArticle

# Credibility tiers, from config/sources.yaml.
TIER_PRIMARY = 1
TIER_ESTABLISHED = 2

FRESHNESS_HOURS = 24.0

# Weights. Breadth dominates, then tier, then recency as a tie-shaper.
BREADTH_CAP = 4
TIER_BONUS = {1: 2.0, 2: 1.0, 3: 0.0}
RECENCY_WEIGHT = 1.5

_WORD = re.compile(r"[a-z0-9]+")

# Dropped before comparing headlines: they carry no topical signal.
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "with",
        "after",
        "over",
        "into",
        "new",
        "says",
        "said",
        "will",
        "amid",
        "ahead",
        "about",
    ]
)

TITLE_SIMILARITY_THRESHOLD = 0.5

# A run of 8 words matching exactly, by chance, between two independently
# written articles about the same event is vanishingly unlikely — this is
# the same specificity principle as the Writer's own copy check
# (app/agents/writing.py's MAX_VERBATIM_WORDS), applied here to whole
# articles instead of one sentence against a passage.
SYNDICATION_SHINGLE_SIZE = 8
SYNDICATION_OVERLAP_THRESHOLD = 0.5


def _shingles(text: str, size: int = SYNDICATION_SHINGLE_SIZE) -> frozenset[tuple[str, ...]]:
    words = _WORD.findall(text.lower())
    if len(words) < size:
        return frozenset({tuple(words)}) if words else frozenset()
    return frozenset(tuple(words[i : i + size]) for i in range(len(words) - size + 1))


def syndication_overlap(left: CollectedArticle, right: CollectedArticle) -> float:
    """Fraction of the shorter article's word-shingles that also appear in
    the other. High overlap means one is a lightly rewritten copy of the
    other — syndicated wire copy, not independent reporting — which plain
    text equality (the Collector's content hash) does not catch."""
    left_shingles, right_shingles = _shingles(left.text), _shingles(right.text)
    if not left_shingles or not right_shingles:
        return 0.0
    shared = len(left_shingles & right_shingles)
    return shared / min(len(left_shingles), len(right_shingles))


def _stem(word: str) -> str:
    """A deliberately narrow suffix strip — plurals and past tense only, not
    a full stemmer, so it merges morphological variants of the same word
    ("tax"/"taxes") without collapsing genuinely different words together
    the way a more aggressive stemmer would ("approves" stays distinct from
    "clears" — that's a paraphrase, which is the LLM step's job to catch,
    not this deterministic fallback's).
    """
    if word.endswith("ies") and len(word) > 5:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 4:
        return word[:-2]
    if word.endswith("ed") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def title_tokens(title: str) -> frozenset[str]:
    return frozenset(
        _stem(w) for w in _WORD.findall(title.lower()) if w not in _STOPWORDS and len(w) > 2
    )


def title_similarity(left: str, right: str) -> float:
    a, b = title_tokens(left), title_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# CLAUDE.md: "Conflicting key facts -> state that reports differ, or drop."
# This can only ever say "these two sentences read like the same claim with
# different figures," never resolve which source is right, so a drop is the
# only response that doesn't risk publishing a guess.
CONFLICTING_FACTS_CONTEXT_THRESHOLD = 0.6

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _sentence_context(sentence: str) -> frozenset[str]:
    """Like title_tokens, but with pure-number tokens excluded — they're
    exactly what this check needs to vary, not match on."""
    return frozenset(token for token in title_tokens(sentence) if not token.isdigit())


def conflicting_facts(articles: Sequence[CollectedArticle]) -> list[str]:
    """Sentence pairs, from different articles in the same cluster, whose
    surrounding wording matches closely but whose numbers don't share a
    single value — the same specificity principle as syndication_overlap,
    pointed at disagreement instead of duplication.

    Deliberately conservative: most real conflicts won't phrase the
    disagreement in near-identical sentences, so this misses plenty. It is
    a floor, not a complete solution — same posture as the deterministic
    clustering fallback.
    """
    sentences = [
        (article.source_key, sentence)
        for article in articles
        for sentence in _SENTENCE_SPLIT.split(article.text.strip())
        if sentence
    ]

    conflicts: list[str] = []
    for index, (source_a, sentence_a) in enumerate(sentences):
        numbers_a = numbers_in(sentence_a)
        if not numbers_a:
            continue
        context_a = _sentence_context(sentence_a)
        if not context_a:
            continue

        for source_b, sentence_b in sentences[index + 1 :]:
            if source_b == source_a:
                continue  # the same outlet repeating itself is not a conflict

            numbers_b = numbers_in(sentence_b)
            if not numbers_b or numbers_a & numbers_b:
                continue  # no numbers to disagree on, or they share one

            context_b = _sentence_context(sentence_b)
            if not context_b:
                continue

            overlap = len(context_a & context_b) / len(context_a | context_b)
            if overlap >= CONFLICTING_FACTS_CONTEXT_THRESHOLD:
                conflicts.append(
                    f"{source_a} ({sorted(numbers_a)}) vs {source_b} ({sorted(numbers_b)}): "
                    f"{sentence_a!r} / {sentence_b!r}"
                )

    return conflicts


def cluster_by_title(
    articles: Mapping[str, CollectedArticle],
    *,
    threshold: float = TITLE_SIMILARITY_THRESHOLD,
) -> list[list[str]]:
    """Deterministic fallback clustering by headline overlap.

    Used when the model is unavailable. Cruder than the model, but it never
    invents a grouping, and a duplicated story is a quality problem rather
    than a factual one.
    """
    clusters: list[list[str]] = []
    for article_id, article in articles.items():
        for cluster in clusters:
            representative = articles[cluster[0]].title
            if title_similarity(representative, article.title) >= threshold:
                cluster.append(article_id)
                break
        else:
            clusters.append([article_id])
    return clusters


def reconcile_clusters(
    proposed: Sequence[Sequence[str]],
    articles: Mapping[str, CollectedArticle],
) -> list[list[str]]:
    """Force a model's proposed grouping to be a valid partition.

    Ids it invented are discarded, an article assigned twice keeps its first
    placement, and anything it forgot becomes its own cluster. The model can
    therefore only influence grouping, never the article set.
    """
    assigned: set[str] = set()
    clusters: list[list[str]] = []

    for group in proposed:
        members = [
            article_id
            for article_id in dict.fromkeys(group)
            if article_id in articles and article_id not in assigned
        ]
        if not members:
            continue
        assigned.update(members)
        clusters.append(members)

    clusters.extend([article_id] for article_id in articles if article_id not in assigned)
    return clusters


def independent_sources(articles: Sequence[CollectedArticle], tiers: Mapping[str, int]) -> int:
    """Count distinct tier-1/2 *voices* — not just distinct source keys.

    Two outlets running the same wire copy are not truly independent.
    Identical text is already caught by the Collector's content hash before
    this ever runs; a lightly rewritten syndication is caught here instead,
    by shingle overlap (`syndication_overlap`), so it counts as one voice
    rather than two.
    """
    eligible = [a for a in articles if tiers.get(a.source_key, 3) <= TIER_ESTABLISHED]
    voices: list[CollectedArticle] = []
    for article in eligible:
        if any(article.source_key == voice.source_key for voice in voices):
            continue
        if any(
            syndication_overlap(article, voice) >= SYNDICATION_OVERLAP_THRESHOLD for voice in voices
        ):
            continue
        voices.append(article)
    return len(voices)


def best_tier(articles: Sequence[CollectedArticle], tiers: Mapping[str, int]) -> int:
    return min((tiers.get(article.source_key, 3) for article in articles), default=3)


def corroboration_for(
    articles: Sequence[CollectedArticle], tiers: Mapping[str, int]
) -> Corroboration:
    if best_tier(articles, tiers) == TIER_PRIMARY:
        return Corroboration.PRIMARY_OFFICIAL
    if independent_sources(articles, tiers) >= 2:
        return Corroboration.CORROBORATED
    if independent_sources(articles, tiers) == 1:
        return Corroboration.SINGLE_SOURCE
    return Corroboration.TIER3_ONLY


def meets_gate(corroboration: Corroboration, *, strict: bool) -> bool:
    """Strict genres (india, politics, business) need real corroboration."""
    if not strict:
        return True
    return corroboration in (Corroboration.PRIMARY_OFFICIAL, Corroboration.CORROBORATED)


def score_cluster(
    articles: Sequence[CollectedArticle],
    tiers: Mapping[str, int],
    *,
    now: datetime,
) -> float:
    breadth = float(min(independent_sources(articles, tiers), BREADTH_CAP))
    tier = TIER_BONUS.get(best_tier(articles, tiers), 0.0)

    newest = max(article.published_at for article in articles)
    age_hours = max((now - newest).total_seconds() / 3600.0, 0.0)
    recency = max(0.0, 1.0 - age_hours / FRESHNESS_HOURS) * RECENCY_WEIGHT

    return breadth + tier + recency

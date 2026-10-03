"""Weekend edition content: Saturday's "longer reads", Sunday's "weekly
recap", and the weekend quiz. No LLM.

CLAUDE.md: Saturday is the day's top stories plus "longer reads" (extended
summaries of the week's most significant verified stories); Sunday is the
day's top stories plus a "weekly recap" (built from stories already
verified and published Mon-Sat); both weekend days also carry a quiz. The
day's own top stories need no code here — that is the ordinary per-genre
build every day gets. What is new is looking back across several already-
published days rather than at just one, so everything below reads stories
that were written, cited and fact-checked earlier in the week and never
invents new text — the quiz's "wrong" answers are themselves real,
verified headlines from other stories, not manufactured distractors.

Which features actually run on a given Saturday/Sunday comes from
config/editions.yaml's `weekend.saturday_features`/`sunday_features`
rather than being hardcoded here.
"""

from __future__ import annotations

import dataclasses
import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config.loader import load_editions
from app.config.schemas import EditionsConfig
from app.models.content import WeekendFeature
from app.models.enums import WeekendFeatureKind
from app.render.selection import Candidate, SourceLink, load_week_candidates

# A story only counts as "significant" if it was among its own genre's
# best-ranked that day — a rank-5 story is real news, but not week-in-review
# news.
SIGNIFICANT_POOL_RANK_MAX = 3
LONGER_READS_LIMIT = 6
WEEKLY_RECAP_LIMIT = 12
QUIZ_QUESTIONS = 5
QUIZ_OPTIONS = 4


def week_dates_before(edition_date: date) -> list[date]:
    """Monday of `edition_date`'s week, up to (not including) `edition_date`.

    Saturday (weekday 5) gets Monday-Friday; Sunday (weekday 6) gets
    Monday-Saturday — exactly the ranges CLAUDE.md describes for each.
    """
    monday = edition_date - timedelta(days=edition_date.weekday())
    return [monday + timedelta(days=offset) for offset in range(edition_date.weekday())]


def _significant(candidates: Sequence[Candidate]) -> list[Candidate]:
    ranked = [c for c in candidates if c.pool_rank <= SIGNIFICANT_POOL_RANK_MAX]
    return sorted(ranked, key=lambda c: (c.pool_rank, str(c.story_id)))


@dataclass(frozen=True)
class LongerRead:
    genre: str
    headline: str
    summary: str
    why_this_matters: str | None
    hedged: bool
    sources: tuple[SourceLink, ...]


@dataclass(frozen=True)
class RecapItem:
    genre: str
    headline: str
    one_liner: str | None
    sources: tuple[SourceLink, ...]


@dataclass(frozen=True)
class QuizQuestion:
    question: str
    options: tuple[str, ...]
    correct_index: int
    source_name: str
    source_url: str


@dataclass(frozen=True)
class WeekendContent:
    longer_reads: tuple[LongerRead, ...] = ()
    weekly_recap: tuple[RecapItem, ...] = ()
    quiz: tuple[QuizQuestion, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.longer_reads or self.weekly_recap or self.quiz)


def build_longer_reads(candidates: Sequence[Candidate]) -> tuple[LongerRead, ...]:
    picked = _significant(candidates)[:LONGER_READS_LIMIT]
    return tuple(
        LongerRead(
            genre=c.genre,
            headline=c.headline,
            summary=c.summary,
            why_this_matters=c.why_this_matters,
            hedged=c.hedged,
            sources=c.sources,
        )
        for c in picked
    )


def build_weekly_recap(candidates: Sequence[Candidate]) -> tuple[RecapItem, ...]:
    picked = _significant(candidates)[:WEEKLY_RECAP_LIMIT]
    return tuple(
        RecapItem(genre=c.genre, headline=c.headline, one_liner=c.one_liner, sources=c.sources)
        for c in picked
    )


def build_quiz(candidates: Sequence[Candidate], *, edition_date: date) -> tuple[QuizQuestion, ...]:
    """Multiple-choice: the real headline against decoys drawn from other
    verified stories the same week. Every option is a headline that was
    itself already fact-checked, and the answer links straight back to its
    source — nothing here is invented.
    """
    pool = _significant(candidates)
    if len(pool) < QUIZ_OPTIONS:
        return ()

    # Seeded only by the edition date: the same edition produces the same
    # quiz however many times a build reruns.
    rng = random.Random(edition_date.isoformat())
    questions: list[QuizQuestion] = []
    for correct in pool[:QUIZ_QUESTIONS]:
        decoys = rng.sample([c for c in pool if c.story_id != correct.story_id], QUIZ_OPTIONS - 1)
        options = [correct, *decoys]
        rng.shuffle(options)
        source = correct.sources[0] if correct.sources else SourceLink(name="", url="")
        questions.append(
            QuizQuestion(
                question=f"Which of these actually happened in {correct.genre} this week?",
                options=tuple(o.headline for o in options),
                correct_index=options.index(correct),
                source_name=source.name,
                source_url=source.url,
            )
        )
    return tuple(questions)


# ------------------------------------------------------------- persistence

_BUILDERS: dict[str, WeekendFeatureKind] = {
    "longer-reads": WeekendFeatureKind.LONGER_READS,
    "weekly-recap": WeekendFeatureKind.WEEKLY_RECAP,
    "quiz": WeekendFeatureKind.QUIZ,
}


def persist_weekend_features(
    session: Session, *, edition_date: date, editions: EditionsConfig | None = None
) -> tuple[WeekendFeature, ...]:
    """Build and store this weekend edition's features. A no-op on a
    weekday. Safe to rerun: replaces whatever this edition_date already had.
    """
    weekday = edition_date.weekday()
    if weekday == 5:
        feature_keys = (editions or load_editions()).weekend.saturday_features
    elif weekday == 6:
        feature_keys = (editions or load_editions()).weekend.sunday_features
    else:
        return ()

    session.execute(delete(WeekendFeature).where(WeekendFeature.edition_date == edition_date))

    candidates = load_week_candidates(session, dates=week_dates_before(edition_date))
    if not candidates:
        session.flush()
        return ()

    rows: list[WeekendFeature] = []
    for key in feature_keys:
        kind = _BUILDERS.get(key)
        if kind is None:  # "top-stories" and anything else needs no row here
            continue
        items: Sequence[object]
        if kind is WeekendFeatureKind.LONGER_READS:
            items = build_longer_reads(candidates)
        elif kind is WeekendFeatureKind.WEEKLY_RECAP:
            items = build_weekly_recap(candidates)
        else:
            items = build_quiz(candidates, edition_date=edition_date)
        if items:
            rows.append(
                WeekendFeature(
                    edition_date=edition_date,
                    kind=kind,
                    payload={"items": [dataclasses.asdict(item) for item in items]},
                )
            )

    session.add_all(rows)
    session.flush()
    return tuple(rows)


def enabled_weekend_kinds(
    edition_date: date, editions: EditionsConfig | None = None
) -> frozenset[WeekendFeatureKind]:
    """The weekend features the config switches on for this weekday."""
    weekday = edition_date.weekday()
    config = (editions or load_editions()).weekend
    if weekday == 5:
        keys = config.saturday_features
    elif weekday == 6:
        keys = config.sunday_features
    else:
        keys = []
    return frozenset(_BUILDERS[key] for key in keys if key in _BUILDERS)


def load_weekend_features(
    session: Session, *, edition_date: date, editions: EditionsConfig | None = None
) -> WeekendContent:
    """Read back what `persist_weekend_features` stored for this date, limited to the
    features the config has switched on - so a feature that was stored before it was
    turned off (the quiz, 2026-10-03) can never reach a reader."""
    enabled = enabled_weekend_kinds(edition_date, editions)
    by_kind: dict[WeekendFeatureKind, list[dict[str, Any]]] = {
        row.kind: row.payload["items"]
        for row in session.scalars(
            select(WeekendFeature).where(WeekendFeature.edition_date == edition_date)
        )
        if row.kind in enabled
    }

    longer_reads = tuple(
        LongerRead(
            genre=item["genre"],
            headline=item["headline"],
            summary=item["summary"],
            why_this_matters=item["why_this_matters"],
            hedged=item["hedged"],
            sources=tuple(SourceLink(**s) for s in item["sources"]),
        )
        for item in by_kind.get(WeekendFeatureKind.LONGER_READS, [])
    )
    weekly_recap = tuple(
        RecapItem(
            genre=item["genre"],
            headline=item["headline"],
            one_liner=item["one_liner"],
            sources=tuple(SourceLink(**s) for s in item["sources"]),
        )
        for item in by_kind.get(WeekendFeatureKind.WEEKLY_RECAP, [])
    )
    quiz = tuple(
        QuizQuestion(
            question=item["question"],
            options=tuple(item["options"]),
            correct_index=item["correct_index"],
            source_name=item["source_name"],
            source_url=item["source_url"],
        )
        for item in by_kind.get(WeekendFeatureKind.QUIZ, [])
    )
    return WeekendContent(longer_reads=longer_reads, weekly_recap=weekly_recap, quiz=quiz)

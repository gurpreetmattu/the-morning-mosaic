"""Agent 1 — Orchestrator.

Runs each genre through collect -> rank -> write-and-verify, enforces the
build deadline, isolates failures, and applies the special-edition calendar.

Deliberately contains no LLM call. Every responsibility here is control flow:
which genre runs next, whether the deadline has passed, whether a section has
enough verified stories to publish. Routing a build through a model would make
it non-reproducible, and would make deadline enforcement depend on a call that
can itself hang. CLAUDE.md's agent table lists this agent as code-only, to match.

The Orchestrator supervises the per-genre pipeline; it is not itself a graph
node. Each genre's actual collect -> rank -> verify work is a LangGraph graph
(`app/graph/build_genre.py`) — this module decides which genres run, runs
them in parallel bounded by `max_workers`, and isolates one genre's exception
from the rest, none of which is a step inside any single genre's own graph.

Failure policy, from CLAUDE.md:
- a genre that fails or misses the deadline has its section omitted;
- fewer than `min_stories` verified leaves a short "quiet news day" note;
- one genre's failure never touches another's.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from typing import TypeVar

from app.agents.crossgenre import CrossGenreResult, StoryMark, assign_owners
from app.agents.schemas import EditionBuild, GenreOutcome
from app.clock import now_utc
from app.config.loader import load_editions, load_genres
from app.config.schemas import EditionsConfig, GenreKey, GenresConfig
from app.graph.build_genre import (
    FAILED_NOTE,
    QUIET_DAY_NOTE,
    CollectorLike,
    Prepared,
    RankerLike,
    VerifyFn,
    finish,
    prepare,
)
from app.graph.build_genre import run as run_build_genre
from app.models.enums import SectionStatus

__all__ = [
    "FAILED_NOTE",
    "QUIET_DAY_NOTE",
    "CollectorLike",
    "Orchestrator",
    "RankerLike",
    "VerifyFn",
]

logger = logging.getLogger(__name__)

_T = TypeVar("_T")
_R = TypeVar("_R")

# Genres run in parallel, bounded so the free-tier gateway is not overrun.
DEFAULT_MAX_WORKERS = 3


class Orchestrator:
    def __init__(
        self,
        *,
        collector: CollectorLike,
        ranker: RankerLike,
        verify: VerifyFn,
        genres: GenresConfig | None = None,
        editions: EditionsConfig | None = None,
        max_workers: int = DEFAULT_MAX_WORKERS,
        clock: Callable[[], datetime] = now_utc,
    ) -> None:
        self._collector = collector
        self._ranker = ranker
        self._verify = verify
        self._genres = genres or load_genres()
        self._editions = editions or load_editions()
        self._max_workers = max(1, max_workers)
        self._clock = clock

    # ------------------------------------------------------------- the build

    def build(
        self,
        *,
        edition_date: date,
        deadline: datetime,
        genres: list[GenreKey] | None = None,
        now: datetime | None = None,
        published: Sequence[StoryMark] = (),
    ) -> EditionBuild:
        """Run the genres in two parallel halves with a deduplication step between them.

        Every genre collects and ranks first. Then, in code and in fixed priority order, each
        story that two genres both pooled is kept by one of them only, so verification time
        is never spent on a story the edition will not print twice. `published` are stories
        already out for this edition (a late update); new candidates repeating them elsewhere
        are dropped too.
        """
        targets = genres if genres is not None else self._genres.active_keys
        reference = now or self._clock()

        prepared = self._map(
            lambda g: self._prepare_safely(g, deadline=deadline, now=reference), targets
        )
        shared = assign_owners(
            {p.genre: p.candidates for p in prepared if p.outcome is None},
            order=self._genres.dedup_order,
            published=published,
        )
        self._log_cross_genre(shared)
        outcomes = self._map(lambda p: self._finish_safely(p, shared), prepared)

        special = self._editions.for_date(edition_date)
        return EditionBuild(
            edition_date=edition_date,
            edition_number=self.edition_number(edition_date),
            special_edition_key=special.key if special else None,
            is_weekend=edition_date.weekday() >= 5,
            genres=outcomes,
            deadline_missed=any(outcome.deadline_hit for outcome in outcomes),
        )

    def _map(self, fn: Callable[[_T], _R], items: Sequence[_T]) -> list[_R]:
        """`fn` over `items` in order, in parallel up to `max_workers`."""
        if self._max_workers == 1:
            return [fn(item) for item in items]
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            return list(pool.map(fn, items))

    @staticmethod
    def _log_cross_genre(shared: CrossGenreResult) -> None:
        for genre, labels in shared.dropped.items():
            logger.info(
                "cross_genre_duplicates_dropped",
                extra={"genre": genre, "count": len(labels)},
            )

    def edition_number(self, edition_date: date) -> int:
        """Sequential count of daily editions since launch; revisions share it."""
        offset = (edition_date - self._editions.launch_date).days
        if offset < 0:
            raise ValueError(
                f"{edition_date} precedes launch_date {self._editions.launch_date}; "
                "set a real launch_date in config/editions.yaml"
            )
        return offset + 1

    # -------------------------------------------------------------- one genre

    def _prepare_safely(self, genre: GenreKey, *, deadline: datetime, now: datetime) -> Prepared:
        settings = self._genres.by_key()[genre]
        try:
            return prepare(
                collector=self._collector,
                ranker=self._ranker,
                verify=self._verify,
                clock=self._clock,
                genre=genre,
                deadline=deadline,
                now=now,
                pool_size=settings.pool_size,
                min_stories=settings.min_stories,
            )
        except Exception:
            # One genre must never take the edition down with it.
            logger.exception("genre build failed", extra={"genre": genre})
            return Prepared(
                genre=genre,
                outcome=GenreOutcome(genre=genre, status=SectionStatus.FAILED, note=FAILED_NOTE),
                candidates=[],
                _state={},
            )

    def _finish_safely(self, prepared: Prepared, shared: CrossGenreResult) -> GenreOutcome:
        try:
            return finish(
                prepared,
                candidates=shared.kept.get(prepared.genre, prepared.candidates),
                cross_genre_dropped=shared.dropped_count(prepared.genre),
            )
        except Exception:
            logger.exception("genre build failed", extra={"genre": prepared.genre})
            return GenreOutcome(genre=prepared.genre, status=SectionStatus.FAILED, note=FAILED_NOTE)

    def build_genre(self, genre: GenreKey, *, deadline: datetime, now: datetime) -> GenreOutcome:
        settings = self._genres.by_key()[genre]
        return run_build_genre(
            collector=self._collector,
            ranker=self._ranker,
            verify=self._verify,
            clock=self._clock,
            genre=genre,
            deadline=deadline,
            now=now,
            pool_size=settings.pool_size,
            min_stories=settings.min_stories,
        )

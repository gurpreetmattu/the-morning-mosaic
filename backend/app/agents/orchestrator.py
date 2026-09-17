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
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

from app.agents.schemas import EditionBuild, GenreOutcome
from app.clock import now_utc
from app.config.loader import load_editions, load_genres
from app.config.schemas import EditionsConfig, GenreKey, GenresConfig
from app.graph.build_genre import FAILED_NOTE, QUIET_DAY_NOTE, CollectorLike, RankerLike, VerifyFn
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
    ) -> EditionBuild:
        targets = genres if genres is not None else [g.key for g in self._genres.genres]
        reference = now or self._clock()

        outcomes: list[GenreOutcome] = []
        if self._max_workers == 1:
            outcomes = [self._safely(g, deadline=deadline, now=reference) for g in targets]
        else:
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                outcomes = list(
                    pool.map(
                        lambda g: self._safely(g, deadline=deadline, now=reference),
                        targets,
                    )
                )

        special = self._editions.for_date(edition_date)
        return EditionBuild(
            edition_date=edition_date,
            edition_number=self.edition_number(edition_date),
            special_edition_key=special.key if special else None,
            is_weekend=edition_date.weekday() >= 5,
            genres=outcomes,
            deadline_missed=any(outcome.deadline_hit for outcome in outcomes),
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

    def _safely(self, genre: GenreKey, *, deadline: datetime, now: datetime) -> GenreOutcome:
        try:
            return self.build_genre(genre, deadline=deadline, now=now)
        except Exception:
            # One genre must never take the edition down with it.
            logger.exception("genre build failed", extra={"genre": genre})
            return GenreOutcome(genre=genre, status=SectionStatus.FAILED, note=FAILED_NOTE)

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

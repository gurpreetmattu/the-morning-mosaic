"""The write-and-verify loop.

CLAUDE.md: "Unsupported claim -> back to Writer with the specific error. Max 2
retries. If the core headline/summary still fails, drop the story."

The Writer and Fact-checker know nothing about each other; this joins them.
The retry loop itself is a LangGraph graph (`app/graph/write_and_verify.py`)
rather than a hand-rolled Python loop — CLAUDE.md's own architecture diagram
already draws it as one: `checker -->|feedback on failure, max 2 retries|
writer`. This module stays as the stable call site every agent build wires
into, so nothing outside `app/graph` needs to know a graph is involved.
"""

from __future__ import annotations

from app.agents.fact_checker import FactChecker
from app.agents.schemas import PooledStory, VerificationOutcome
from app.agents.writer import Writer
from app.agents.writing import build_passages
from app.config.schemas import GenreKey
from app.graph.write_and_verify import MAX_RETRIES
from app.graph.write_and_verify import run as run_write_and_verify


def write_and_verify(
    *,
    writer: Writer,
    checker: FactChecker,
    pooled: PooledStory,
    genre: GenreKey,
    max_retries: int = MAX_RETRIES,
) -> VerificationOutcome:
    passages = build_passages(pooled.articles)
    return run_write_and_verify(
        writer=writer,
        checker=checker,
        pooled=pooled,
        genre=genre,
        passages=passages,
        max_retries=max_retries,
    )

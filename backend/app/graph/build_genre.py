"""One genre's collect -> rank -> verify pipeline, as a LangGraph graph.

Agents 2-3 (Collector, Ranker) live here; agents 4-5 (Writer, Fact-checker)
are the injected `verify` callable, itself another graph
(`app/graph/write_and_verify.py`) — this graph's "verify one candidate"
node invokes it once per pooled story rather than embedding it directly, so
the retry loop only exists in one place.

Agent 1 (the Orchestrator) supervises this graph rather than being a node in
it: it decides which genres run, runs them in parallel, and isolates one
genre's exception from the others (`app/agents/orchestrator.py`) — none of
which is a step in any single genre's own pipeline.

Failure policy, from CLAUDE.md, encoded as graph routing rather than a
hand-rolled sequence of early returns:
- past the deadline before starting -> fail without fetching anything;
- nothing collected -> a quiet day, not a failure;
- the deadline stops verification but keeps whatever already verified;
- fewer than `min_stories` verified -> a quiet day.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol, TypedDict, cast

from langgraph.graph import END, StateGraph

from app.agents.schemas import (
    GenreOutcome,
    PooledStory,
    StoryPool,
    VerificationOutcome,
    VerifiedStory,
)
from app.config.schemas import GenreKey
from app.models.enums import SectionStatus
from app.sources.schemas import CollectionResult

QUIET_DAY_NOTE = "A quiet news day: too few stories met our sourcing bar."
FAILED_NOTE = "This section could not be prepared in time."


class CollectorLike(Protocol):
    """Structural, so a test can substitute a stub without a network."""

    def collect(self, genre: GenreKey, *, now: datetime | None = None) -> CollectionResult: ...


class RankerLike(Protocol):
    def rank(self, collected: CollectionResult, *, now: datetime | None = None) -> StoryPool: ...


VerifyFn = Callable[[PooledStory, GenreKey], VerificationOutcome]


class _State(TypedDict, total=False):
    collector: CollectorLike
    ranker: RankerLike
    verify: VerifyFn
    clock: Callable[[], datetime]
    genre: GenreKey
    deadline: datetime
    now: datetime
    pool_size: int
    min_stories: int
    collected: CollectionResult | None
    candidates: list[PooledStory]
    index: int
    verified: list[VerifiedStory]
    attempted: int
    cut_short: bool
    collected_count: int
    pooled_count: int
    done_verifying: bool
    result: GenreOutcome | None


def _past_deadline(state: _State) -> bool:
    return state["clock"]() >= state["deadline"]


def _check_start_deadline(state: _State) -> dict[str, object]:
    if _past_deadline(state):
        return {
            "result": GenreOutcome(
                genre=state["genre"],
                status=SectionStatus.FAILED,
                note=FAILED_NOTE,
                deadline_hit=True,
            )
        }
    return {}


def _collect(state: _State) -> dict[str, object]:
    collected = state["collector"].collect(state["genre"], now=state["now"])
    if not collected.articles:
        return {
            "result": GenreOutcome(
                genre=state["genre"], status=SectionStatus.QUIET_DAY, note=QUIET_DAY_NOTE
            )
        }
    return {"collected": collected}


def _rank(state: _State) -> dict[str, object]:
    collected = state["collected"]
    assert collected is not None  # only reachable once _collect has set it
    pool = state["ranker"].rank(collected, now=state["now"])
    return {
        "candidates": pool.stories[: state["pool_size"]],
        "collected_count": len(collected.articles),
        "pooled_count": len(pool.stories),
        "index": 0,
        "verified": [],
        "attempted": 0,
        "cut_short": False,
    }


def _verify_step(state: _State) -> dict[str, object]:
    candidates = state["candidates"]
    index = state["index"]
    if index >= len(candidates):
        return {"done_verifying": True}
    if _past_deadline(state):
        # Stop cleanly and keep what is already verified rather than
        # throwing away good work.
        return {"done_verifying": True, "cut_short": True}

    outcome = state["verify"](candidates[index], state["genre"])
    verified = state["verified"]
    if outcome.verified is not None:
        verified = [*verified, outcome.verified]
    return {
        "index": index + 1,
        "attempted": state["attempted"] + 1,
        "verified": verified,
        "done_verifying": False,
    }


def _finalize(state: _State) -> dict[str, object]:
    verified = state["verified"]
    if len(verified) < state["min_stories"]:
        return {
            "result": GenreOutcome(
                genre=state["genre"],
                status=SectionStatus.QUIET_DAY,
                collected=state["collected_count"],
                pooled=state["pooled_count"],
                attempted=state["attempted"],
                note=QUIET_DAY_NOTE,
                deadline_hit=state["cut_short"],
            )
        }
    return {
        "result": GenreOutcome(
            genre=state["genre"],
            status=SectionStatus.OK,
            stories=verified,
            collected=state["collected_count"],
            pooled=state["pooled_count"],
            attempted=state["attempted"],
            deadline_hit=state["cut_short"],
        )
    }


def _after_start_deadline(state: _State) -> str:
    return END if state.get("result") is not None else "collect"


def _after_collect(state: _State) -> str:
    return END if state.get("result") is not None else "rank"


def _after_verify_step(state: _State) -> str:
    return "finalize" if state.get("done_verifying") else "verify_step"


def _build_graph() -> StateGraph[_State, None, _State, _State]:
    graph: StateGraph[_State, None, _State, _State] = StateGraph(_State)
    graph.add_node("check_start_deadline", _check_start_deadline)
    graph.add_node("collect", _collect)
    graph.add_node("rank", _rank)
    graph.add_node("verify_step", _verify_step)
    graph.add_node("finalize", _finalize)

    graph.set_entry_point("check_start_deadline")
    graph.add_conditional_edges("check_start_deadline", _after_start_deadline)
    graph.add_conditional_edges("collect", _after_collect)
    graph.add_edge("rank", "verify_step")
    graph.add_conditional_edges("verify_step", _after_verify_step)
    graph.add_edge("finalize", END)
    return graph


_COMPILED = _build_graph().compile()


def run(
    *,
    collector: CollectorLike,
    ranker: RankerLike,
    verify: VerifyFn,
    clock: Callable[[], datetime],
    genre: GenreKey,
    deadline: datetime,
    now: datetime,
    pool_size: int,
    min_stories: int,
) -> GenreOutcome:
    final = cast(
        "_State",
        _COMPILED.invoke(
            {
                "collector": collector,
                "ranker": ranker,
                "verify": verify,
                "clock": clock,
                "genre": genre,
                "deadline": deadline,
                "now": now,
                "pool_size": pool_size,
                "min_stories": min_stories,
                "collected": None,
                "result": None,
            }
        ),
    )
    result = final["result"]
    assert result is not None  # every path through the graph sets it before END
    return result

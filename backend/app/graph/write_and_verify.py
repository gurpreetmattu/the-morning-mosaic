"""The Writer <-> Fact-checker retry loop, as an actual LangGraph graph.

CLAUDE.md: "Unsupported claim -> back to Writer with the specific error.
Max 2 retries. If the core headline/summary still fails, drop the story."
The architecture diagram draws this as `checker -->|feedback on failure,
max 2 retries| writer` — a loop, which is exactly what `add_conditional_edges`
below encodes instead of a hand-rolled `for` loop.

The Writer and Fact-checker know nothing about each other; this joins them.
Feedback is the Fact-checker's own wording, naming the element and what is
missing, rather than a generic "try again" — re-running an identical prompt
and hoping is not a retry strategy.

The graph is compiled once, at import time, and every call to `run()`
reuses it — only the per-call state (which `Writer`/`FactChecker`, which
story) changes, not the graph shape.
"""

from __future__ import annotations

from typing import TypedDict, cast

from langgraph.graph import END, StateGraph

from app.agents.fact_checker import FactChecker
from app.agents.schemas import (
    PassageRef,
    PooledStory,
    VerificationOutcome,
    VerifiedStory,
    WriterIssue,
    WriterProblem,
    WrittenStory,
)
from app.agents.writer import Writer
from app.config.schemas import GenreKey

MAX_RETRIES = 2


class _State(TypedDict, total=False):
    writer: Writer
    checker: FactChecker
    pooled: PooledStory
    genre: GenreKey
    passages: dict[str, PassageRef]
    max_retries: int
    feedback: str | None
    attempt: int
    draft: WrittenStory | None
    problems: list[WriterProblem]
    result: VerificationOutcome | None


def _problems_as_feedback(problems: list[WriterProblem]) -> str:
    return "\n".join(f"- {problem.issue.value}: {problem.detail}" for problem in problems)


def _write(state: _State) -> dict[str, object]:
    attempt = state["attempt"] + 1
    written = state["writer"].write(state["pooled"], state["genre"], feedback=state["feedback"])

    if written.story is None:
        feedback = _problems_as_feedback(written.problems)
        if any(p.issue is WriterIssue.MODEL_UNAVAILABLE for p in written.problems):
            # The Writer's model is down: a retry would just ask it again.
            return _abandon(attempt, feedback)
        return _retry_or_give_up(attempt, state, feedback)

    copied = [p for p in written.problems if p.issue is WriterIssue.COPIED_TEXT]
    if copied:
        # validate_draft() drops a copied sentence rather than failing the
        # story outright, so a story can come back here missing a sentence
        # it silently lost. Accepting it would publish disjointed prose;
        # retry instead, same as any other rejection, without ever calling
        # the Fact-checker on it.
        return _retry_or_give_up(attempt, state, _problems_as_feedback(copied))

    return {"attempt": attempt, "draft": written.story, "problems": written.problems}


def _check(state: _State) -> dict[str, object]:
    draft = state["draft"]
    assert draft is not None  # only reachable via _after_write's "check" branch
    checked = state["checker"].check(draft, state["passages"])
    if checked.passed:
        assert checked.story is not None
        return {
            "result": VerificationOutcome(
                verified=VerifiedStory(
                    story=checked.story,
                    articles=list(state["pooled"].articles),
                    pool_rank=state["pooled"].rank,
                    findings=checked.findings,
                    attempts=state["attempt"],
                ),
                attempts=state["attempt"],
            )
        }
    feedback = checked.feedback or _problems_as_feedback(state["problems"])
    if checked.unavailable:
        # The checker's model is down. Fail closed, but do not rewrite a story that
        # nothing is able to judge.
        return _abandon(state["attempt"], feedback)
    return _retry_or_give_up(state["attempt"], state, feedback)


def _abandon(attempt: int, feedback: str) -> dict[str, object]:
    return {
        "attempt": attempt,
        "result": VerificationOutcome(
            verified=None,
            attempts=attempt,
            reason=feedback or "no verifiable story after all attempts",
        ),
    }


def _retry_or_give_up(attempt: int, state: _State, feedback: str) -> dict[str, object]:
    if attempt >= state["max_retries"] + 1:
        return _abandon(attempt, feedback)
    return {"attempt": attempt, "feedback": feedback, "draft": None}


def _after_write(state: _State) -> str:
    if state.get("result") is not None:
        return END
    return "check" if state.get("draft") is not None else "write"


def _after_check(state: _State) -> str:
    return END if state.get("result") is not None else "write"


def _build_graph() -> StateGraph[_State, None, _State, _State]:
    graph: StateGraph[_State, None, _State, _State] = StateGraph(_State)
    graph.add_node("write", _write)
    graph.add_node("check", _check)
    graph.set_entry_point("write")
    graph.add_conditional_edges("write", _after_write)
    graph.add_conditional_edges("check", _after_check)
    return graph


_COMPILED = _build_graph().compile()


def run(
    *,
    writer: Writer,
    checker: FactChecker,
    pooled: PooledStory,
    genre: GenreKey,
    passages: dict[str, PassageRef],
    max_retries: int = MAX_RETRIES,
) -> VerificationOutcome:
    final = cast(
        "_State",
        _COMPILED.invoke(
            {
                "writer": writer,
                "checker": checker,
                "pooled": pooled,
                "genre": genre,
                "passages": passages,
                "max_retries": max_retries,
                "feedback": None,
                "attempt": 0,
                "draft": None,
                "problems": [],
                "result": None,
            }
        ),
    )
    result = final["result"]
    assert result is not None  # every path through the graph sets it before END
    return result

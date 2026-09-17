"""app/graph/write_and_verify.py: the Writer <-> Fact-checker retry loop
is a real LangGraph graph, not a Python loop wearing its name.

Behavioral parity with the pre-graph implementation is already
exhaustively covered by test_fact_checker.py's "the loop" tests
(unchanged by this refactor, real Writer/FactChecker instances against a
mocked LLM). What's new here is specific to the graph itself: that it
really is one, and that its retry loop terminates correctly regardless of
how many retries are allowed — using lightweight fakes rather than an LLM,
since this is about the loop's mechanics, not grounding.
"""

from __future__ import annotations

from datetime import UTC, datetime

from langgraph.graph.state import CompiledStateGraph

from app.agents.schemas import (
    CheckResult,
    Corroboration,
    DraftSentence,
    PooledStory,
    WriterIssue,
    WriterProblem,
    WriterResult,
    WrittenStory,
)
from app.graph import write_and_verify
from app.sources.schemas import CollectedArticle, Passage

BODY = "A passage with enough words in it to count as a citable passage body."
NOW = datetime(2026, 10, 5, 4, 15, tzinfo=UTC)


def article() -> CollectedArticle:
    return CollectedArticle(
        source_key="wire",
        genre="business",
        url="https://wire.example/1",
        title="Story",
        published_at=NOW,
        fetched_at=NOW,
        text=BODY,
        passages=[Passage(ordinal=1, text=BODY)],
        content_hash="h1",
    )


def pooled() -> PooledStory:
    return PooledStory(
        event_label="event",
        articles=[article()],
        corroboration=Corroboration.PRIMARY_OFFICIAL,
        hedged=False,
        score=1.0,
        rank=1,
    )


class NeverWrites:
    """Every attempt fails before a story even exists; the checker must
    never be reached."""

    def __init__(self) -> None:
        self.calls = 0

    def write(self, story: PooledStory, genre: str, *, feedback: str | None = None) -> WriterResult:
        self.calls += 1
        return WriterResult(
            problems=[WriterProblem(issue=WriterIssue.UNPARSEABLE, detail="story has no passages")]
        )


class UnreachableChecker:
    def check(self, story: object, passages: object) -> object:
        raise AssertionError("the checker must never run when the writer never produces a story")


def test_the_compiled_graph_is_a_real_langgraph_state_graph() -> None:
    assert isinstance(write_and_verify._COMPILED, CompiledStateGraph)


def test_the_loop_terminates_at_a_large_number_of_retries() -> None:
    """Not the CLAUDE.md-mandated 2, but the loop's own termination logic
    must not depend on that specific small number."""
    writer = NeverWrites()

    outcome = write_and_verify.run(
        writer=writer,  # type: ignore[arg-type]
        checker=UnreachableChecker(),  # type: ignore[arg-type]
        pooled=pooled(),
        genre="business",
        passages={},
        max_retries=30,
    )

    assert outcome.verified is None
    assert outcome.attempts == 31  # one initial attempt plus 30 retries
    assert writer.calls == 31


def test_a_zero_retry_budget_still_gets_one_attempt() -> None:
    writer = NeverWrites()

    outcome = write_and_verify.run(
        writer=writer,  # type: ignore[arg-type]
        checker=UnreachableChecker(),  # type: ignore[arg-type]
        pooled=pooled(),
        genre="business",
        passages={},
        max_retries=0,
    )

    assert outcome.verified is None
    assert outcome.attempts == 1
    assert writer.calls == 1


class WritesThenSucceeds:
    """Fails once, then produces a story every time after."""

    def __init__(self) -> None:
        self.calls = 0

    def write(self, story: PooledStory, genre: str, *, feedback: str | None = None) -> WriterResult:
        self.calls += 1
        if self.calls == 1:
            return WriterResult(
                problems=[WriterProblem(issue=WriterIssue.UNPARSEABLE, detail="first try")]
            )
        return WriterResult(
            story=WrittenStory(
                headline=DraftSentence(text="Headline", passage_ids=["a1:p1"]),
                summary=[DraftSentence(text="Summary.", passage_ids=["a1:p1"])],
            )
        )


class AlwaysPasses:
    def __init__(self) -> None:
        self.calls = 0

    def check(self, story: WrittenStory, passages: object) -> object:
        self.calls += 1
        return CheckResult(story=story)


def test_a_retry_that_eventually_succeeds_never_calls_the_checker_on_the_failed_draft() -> None:
    writer = WritesThenSucceeds()
    checker = AlwaysPasses()

    outcome = write_and_verify.run(
        writer=writer,  # type: ignore[arg-type]
        checker=checker,  # type: ignore[arg-type]
        pooled=pooled(),
        genre="business",
        passages={},
        max_retries=2,
    )

    assert outcome.verified is not None
    assert outcome.attempts == 2
    assert writer.calls == 2
    assert checker.calls == 1  # only for the second, successful draft

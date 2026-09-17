"""app/graph/build_genre.py: the per-genre pipeline is a real LangGraph
graph, not a Python loop wearing its name.

Behavioral parity with the pre-graph implementation (deadlines, the
quiet-day rule, failure isolation) is already exhaustively covered by
test_orchestrator.py, unchanged by this refactor. What's new here is
specific to the graph itself: that it really is one, and that its
per-candidate loop (`verify_step`, one graph step per pooled story) still
verifies every candidate correctly at the largest pool size a genre's
config is allowed to have, not just a conveniently small example.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from langgraph.graph.state import CompiledStateGraph

from app.agents.schemas import (
    Corroboration,
    DraftSentence,
    PooledStory,
    StoryPool,
    VerificationOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.config.schemas import GenreKey
from app.graph import build_genre
from app.models.enums import SectionStatus
from app.sources.schemas import CollectedArticle, CollectionResult, Passage

NOW = datetime(2026, 10, 5, 4, 15, tzinfo=UTC)
DEADLINE = NOW + timedelta(hours=1)

# The real ceiling: config/schemas.py's Genre.pool_size is validated <= 20.
MAX_POOL_SIZE = 20


def article(index: int) -> CollectedArticle:
    text = f"Passage body number {index} with enough words to be a citable one."
    return CollectedArticle(
        source_key="wire",
        genre="india",
        url=f"https://wire.example/{index}",
        title=f"Story {index}",
        published_at=NOW,
        fetched_at=NOW,
        text=text,
        passages=[Passage(ordinal=1, text=text)],
        content_hash=f"h{index}",
    )


def pooled(index: int) -> PooledStory:
    return PooledStory(
        event_label=f"event {index}",
        articles=[article(index)],
        corroboration=Corroboration.PRIMARY_OFFICIAL,
        hedged=False,
        score=1.0,
        rank=index + 1,
    )


def verified(index: int) -> VerifiedStory:
    return VerifiedStory(
        story=WrittenStory(
            headline=DraftSentence(text=f"Headline {index}", passage_ids=["a1:p1"]),
            summary=[DraftSentence(text=f"Summary {index}.", passage_ids=["a1:p1"])],
        ),
        articles=[article(index)],
        pool_rank=max(index, 1),
        attempts=1,
    )


class FakeCollector:
    def __init__(self, count: int) -> None:
        self.count = count

    def collect(self, genre: GenreKey, *, now: datetime | None = None) -> CollectionResult:
        return CollectionResult(genre=genre, articles=[article(i) for i in range(self.count)])


class FakeRanker:
    def __init__(self, count: int) -> None:
        self.count = count

    def rank(self, collected: CollectionResult, *, now: datetime | None = None) -> StoryPool:
        return StoryPool(genre=collected.genre, stories=[pooled(i) for i in range(self.count)])


class AlwaysVerifies:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, story: PooledStory, genre: GenreKey) -> VerificationOutcome:
        self.calls += 1
        return VerificationOutcome(verified=verified(self.calls), attempts=1)


def test_the_compiled_graph_is_a_real_langgraph_state_graph() -> None:
    assert isinstance(build_genre._COMPILED, CompiledStateGraph)


def test_a_pool_at_the_maximum_configured_size_is_verified_in_full() -> None:
    """genres.yaml's pool_size can go up to 20 (config/schemas.py). Every
    candidate is one loop through `verify_step`, so this is the real
    largest case the graph's loop has to get right."""
    verifier = AlwaysVerifies()

    outcome = build_genre.run(
        collector=FakeCollector(MAX_POOL_SIZE),
        ranker=FakeRanker(MAX_POOL_SIZE),
        verify=verifier,
        clock=lambda: NOW,
        genre="india",
        deadline=DEADLINE,
        now=NOW,
        pool_size=MAX_POOL_SIZE,
        min_stories=2,
    )

    assert outcome.status is SectionStatus.OK
    assert verifier.calls == MAX_POOL_SIZE
    assert len(outcome.stories) == MAX_POOL_SIZE

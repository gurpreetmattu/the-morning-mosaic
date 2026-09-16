"""Persisting a built genre into the audit trail."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.schemas import (
    CheckFinding,
    DraftSentence,
    GenreOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.db.persist import PersistError, persist_genre
from app.db.seed import seed_sources
from app.models.content import (
    Article,
    ArticlePassage,
    FactCheck,
    SentenceCitation,
    Story,
    StoryCluster,
    StorySentence,
    StoryTag,
)
from app.models.editions import Edition, EditionRevision
from app.models.enums import (
    CheckMethod,
    ClaimVerdict,
    RevisionReason,
    SectionStatus,
    SentenceRole,
    StoryStatus,
    TagKind,
)
from app.sources.schemas import CollectedArticle, Passage

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 5, 4, 15, tzinfo=UTC)
EDITION = date(2026, 10, 5)

P1 = "The cabinet approved the eastern freight corridor on Tuesday, officials said."
P2 = "The route runs about nine hundred kilometres through three states."


def article(url_suffix: str = "one", source: str = "the-hindu") -> CollectedArticle:
    return CollectedArticle(
        source_key=source,
        genre="india",
        url=f"https://example.test/{url_suffix}",
        title="Cabinet clears corridor",
        author="A Correspondent",
        published_at=NOW,
        fetched_at=NOW,
        text=f"{P1} {P2}",
        passages=[Passage(ordinal=1, text=P1), Passage(ordinal=2, text=P2)],
        content_hash=f"hash-{url_suffix}",
    )


def verified(rank: int = 1, *, articles: list[CollectedArticle] | None = None) -> VerifiedStory:
    return VerifiedStory(
        story=WrittenStory(
            headline=DraftSentence(text="Corridor cleared by cabinet", passage_ids=["a1:p1"]),
            summary=[
                DraftSentence(text="Ministers approved the plan.", passage_ids=["a1:p1"]),
                DraftSentence(text="It spans three states.", passage_ids=["a1:p2"]),
            ],
            one_liner=DraftSentence(text="Corridor approved", passage_ids=["a1:p1"]),
            why_this_matters=[
                DraftSentence(text="Officials framed it as capacity relief.", passage_ids=["a1:p2"])
            ],
            topic_tags=["infrastructure"],
            entity_tags=["cabinet"],
            india_relevance=True,
            model="test-model",
            prompt_version="writer-v1",
        ),
        articles=articles or [article()],
        pool_rank=rank,
        findings=[
            CheckFinding(
                element="headline",
                claim="the cabinet approved it",
                verdict=ClaimVerdict.SUPPORTED,
                method=CheckMethod.LLM,
                detail="",
            ),
            CheckFinding(
                element="summary[0]",
                claim="figures check out",
                verdict=ClaimVerdict.SUPPORTED,
                method=CheckMethod.DETERMINISTIC,
            ),
        ],
        attempts=1,
    )


def outcome(*stories: VerifiedStory) -> GenreOutcome:
    return GenreOutcome(
        genre="india",
        status=SectionStatus.OK,
        stories=list(stories) or [verified()],
        collected=3,
        pooled=2,
        attempted=2,
    )


@pytest.fixture(autouse=True)
def _sources(session: Session) -> None:
    seed_sources(session)
    session.flush()


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


# ------------------------------------------------------------- happy path


def test_a_story_is_written_with_its_sentences_and_citations(session: Session) -> None:
    stored = persist_genre(session, edition_date=EDITION, outcome=outcome())
    assert stored == 1

    story = session.scalar(select(Story))
    assert story is not None
    assert story.status is StoryStatus.VERIFIED
    assert story.headline == "Corridor cleared by cabinet"
    assert story.india_relevance is True
    assert story.model == "test-model"
    assert story.prompt_version == "writer-v1"

    roles = [row.role for row in session.scalars(select(StorySentence))]
    assert roles.count(SentenceRole.HEADLINE) == 1
    assert roles.count(SentenceRole.SUMMARY) == 2
    assert roles.count(SentenceRole.ONE_LINER) == 1
    assert roles.count(SentenceRole.WHY_THIS_MATTERS) == 1


def test_every_citation_resolves_to_a_real_passage(session: Session) -> None:
    persist_genre(session, edition_date=EDITION, outcome=outcome())

    citations = list(session.scalars(select(SentenceCitation)))
    assert len(citations) == 5
    for citation in citations:
        passage = session.get(ArticlePassage, citation.passage_id)
        assert passage is not None
        # The excerpt is frozen, not a reference, so it survives the purge.
        assert citation.excerpt == passage.text


def test_cited_passages_are_flagged_for_permanent_retention(session: Session) -> None:
    persist_genre(session, edition_date=EDITION, outcome=outcome())

    cited = {p.ordinal for p in session.scalars(select(ArticlePassage)) if p.cited}
    assert cited == {1, 2}


def test_tags_and_fact_checks_are_recorded(session: Session) -> None:
    persist_genre(session, edition_date=EDITION, outcome=outcome())

    tags = {(row.kind, row.value) for row in session.scalars(select(StoryTag))}
    assert (TagKind.TOPIC, "infrastructure") in tags
    assert (TagKind.ENTITY, "cabinet") in tags
    assert count(session, FactCheck) == 2


def test_the_pool_rank_survives(session: Session) -> None:
    persist_genre(session, edition_date=EDITION, outcome=outcome(verified(rank=4)))
    story = session.scalar(select(Story))
    assert story is not None
    assert story.pool_rank == 4


def test_a_story_without_a_one_liner_is_storable(session: Session) -> None:
    subject = verified()
    stripped = subject.model_copy(
        update={"story": subject.story.model_copy(update={"one_liner": None})}
    )
    persist_genre(session, edition_date=EDITION, outcome=outcome(stripped))

    story = session.scalar(select(Story))
    assert story is not None
    assert story.one_liner is None


# ----------------------------------------------------------- rerunnability


def test_rerunning_replaces_rather_than_duplicates(session: Session) -> None:
    persist_genre(session, edition_date=EDITION, outcome=outcome())
    persist_genre(session, edition_date=EDITION, outcome=outcome())

    assert count(session, Story) == 1
    assert count(session, StoryCluster) == 1
    # The article is reused, not written twice.
    assert count(session, Article) == 1


def test_an_article_shared_between_stories_is_stored_once(session: Session) -> None:
    shared = article("shared")
    persist_genre(
        session,
        edition_date=EDITION,
        outcome=outcome(verified(1, articles=[shared]), verified(2, articles=[shared])),
    )

    assert count(session, Story) == 2
    assert count(session, Article) == 1
    assert count(session, ArticlePassage) == 2


def test_published_editions_are_never_rewritten(session: Session) -> None:
    edition = Edition(edition_date=EDITION, edition_number=5)
    session.add(edition)
    session.flush()
    session.add(
        EditionRevision(
            edition_id=edition.id, revision=1, reason=RevisionReason.BUILD, published_at=NOW
        )
    )
    session.flush()

    with pytest.raises(PersistError, match="already has a published revision"):
        persist_genre(session, edition_date=EDITION, outcome=outcome())


def test_an_unknown_source_is_refused(session: Session) -> None:
    unknown = article("x", source="not-whitelisted")
    with pytest.raises(PersistError, match="run the seed job"):
        persist_genre(session, edition_date=EDITION, outcome=outcome(verified(articles=[unknown])))


def test_a_quiet_day_stores_nothing(session: Session) -> None:
    quiet = GenreOutcome(genre="india", status=SectionStatus.QUIET_DAY, note="quiet")
    assert persist_genre(session, edition_date=EDITION, outcome=quiet) == 0
    assert count(session, Story) == 0

"""Persist a built genre into the audit trail.

This is where the grounding chain meets the schema. Every published sentence
lands in `story_sentences` with its citations in `sentence_citations`, and each
citation carries a frozen copy of the passage text it relied on, so the trail
survives the 30-day purge of uncited raw article text.

Rerunnability, per "jobs are safe to rerun": re-persisting a genre replaces the
stories previously written for that edition date and genre. That is safe only
before anything has been published, so it refuses outright once a revision
exists for the edition — published content is never rewritten.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.agents.schemas import DraftSentence, GenreOutcome, VerifiedStory
from app.clock import now_utc
from app.models.content import (
    Article,
    ArticlePassage,
    ClusterArticle,
    FactCheck,
    SentenceCitation,
    Source,
    Story,
    StoryCluster,
    StorySentence,
    StoryTag,
)
from app.models.editions import Edition, EditionRevision
from app.models.enums import SentenceRole, StoryStatus, TagKind
from app.sources.schemas import CollectedArticle


class PersistError(RuntimeError):
    """The write was refused rather than risking published content."""


def persist_genre(session: Session, *, edition_date: date, outcome: GenreOutcome) -> int:
    """Write one genre's verified stories. Returns the number stored."""
    _refuse_if_published(session, edition_date)
    _clear_previous(session, edition_date=edition_date, genre=outcome.genre)

    for verified in outcome.stories:
        _store_story(session, edition_date=edition_date, genre=outcome.genre, verified=verified)

    session.flush()
    return len(outcome.stories)


# ------------------------------------------------------------------- guards


def _refuse_if_published(session: Session, edition_date: date) -> None:
    published = session.scalar(
        select(EditionRevision.id)
        .join(Edition, Edition.id == EditionRevision.edition_id)
        .where(Edition.edition_date == edition_date)
        .limit(1)
    )
    if published is not None:
        raise PersistError(
            f"{edition_date} already has a published revision; "
            "publish a new revision instead of rewriting its stories"
        )


def _clear_previous(session: Session, *, edition_date: date, genre: str) -> None:
    """Remove a previous build's stories for this date and genre.

    Sentences, citations, tags and fact checks cascade. Corrections and
    withdrawals use ON DELETE RESTRICT, so a story that has been corrected
    cannot be silently discarded — the delete fails loudly instead.
    """
    session.execute(delete(Story).where(Story.edition_date == edition_date, Story.genre == genre))
    session.execute(
        delete(StoryCluster).where(
            StoryCluster.edition_date == edition_date, StoryCluster.genre == genre
        )
    )
    session.flush()


# -------------------------------------------------------------- the writing


def _store_story(
    session: Session, *, edition_date: date, genre: str, verified: VerifiedStory
) -> Story:
    written = verified.story
    source_articles = verified.articles

    cluster = StoryCluster(edition_date=edition_date, genre=genre)
    session.add(cluster)
    session.flush()

    passages: dict[str, ArticlePassage] = {}
    for index, collected in enumerate(source_articles, start=1):
        article = _upsert_article(session, collected, genre=genre)
        for passage in _upsert_passages(session, article, collected):
            passages[f"a{index}:p{passage.ordinal}"] = passage
        session.add(
            ClusterArticle(cluster_id=cluster.id, article_id=article.id, is_primary=index == 1)
        )

    story = Story(
        cluster_id=cluster.id,
        edition_date=edition_date,
        genre=genre,
        headline=written.headline.text,
        summary=" ".join(sentence.text for sentence in written.summary),
        one_liner=written.one_liner.text if written.one_liner else None,
        why_this_matters=(
            " ".join(sentence.text for sentence in written.why_this_matters)
            if written.why_this_matters
            else None
        ),
        india_relevance=written.india_relevance,
        pool_rank=verified.pool_rank,
        status=StoryStatus.VERIFIED,
        hedged=written.hedged,
        model=written.model,
        prompt_version=written.prompt_version,
    )
    session.add(story)
    session.flush()

    _store_sentences(session, story, verified, passages)
    _store_tags(session, story, verified)
    _store_fact_checks(session, story, verified)
    return story


def _upsert_article(session: Session, collected: CollectedArticle, *, genre: str) -> Article:
    existing = session.scalar(select(Article).where(Article.url == collected.url))
    if existing is not None:
        return existing

    source_id = session.scalar(select(Source.id).where(Source.key == collected.source_key))
    if source_id is None:
        raise PersistError(
            f"source {collected.source_key!r} is not in the database; run the seed job"
        )

    article = Article(
        source_id=source_id,
        url=collected.url,
        canonical_url=collected.canonical_url,
        title=collected.title,
        author=collected.author,
        published_at=collected.published_at,
        fetched_at=collected.fetched_at,
        genre=genre,
        raw_text=collected.text,
        content_hash=collected.content_hash,
    )
    session.add(article)
    session.flush()
    return article


def _upsert_passages(
    session: Session, article: Article, collected: CollectedArticle
) -> list[ArticlePassage]:
    existing = {
        row.ordinal: row
        for row in session.scalars(
            select(ArticlePassage).where(ArticlePassage.article_id == article.id)
        )
    }
    stored: list[ArticlePassage] = []
    for passage in collected.passages:
        row = existing.get(passage.ordinal)
        if row is None:
            row = ArticlePassage(article_id=article.id, ordinal=passage.ordinal, text=passage.text)
            session.add(row)
        stored.append(row)
    session.flush()
    return stored


def _store_sentences(
    session: Session,
    story: Story,
    verified: VerifiedStory,
    passages: dict[str, ArticlePassage],
) -> None:
    written = verified.story
    groups: list[tuple[SentenceRole, list[DraftSentence]]] = [
        (SentenceRole.HEADLINE, [written.headline]),
        (SentenceRole.SUMMARY, list(written.summary)),
        (SentenceRole.WHY_THIS_MATTERS, list(written.why_this_matters)),
    ]
    if written.one_liner is not None:
        groups.append((SentenceRole.ONE_LINER, [written.one_liner]))

    for role, sentences in groups:
        for ordinal, sentence in enumerate(sentences):
            row = StorySentence(
                story_id=story.id,
                role=role,
                ordinal=ordinal,
                text=sentence.text,
            )
            session.add(row)
            session.flush()

            for citation_id in dict.fromkeys(sentence.passage_ids):
                passage = passages.get(citation_id)
                if passage is None:
                    raise PersistError(
                        f"sentence cites {citation_id!r}, which is not among this "
                        "story's passages; the Writer's validation should have caught it"
                    )
                session.add(
                    SentenceCitation(
                        sentence_id=row.id,
                        passage_id=passage.id,
                        # Frozen so the trail survives the raw-text purge.
                        excerpt=passage.text,
                    )
                )
                # Cited passages are kept permanently.
                passage.cited = True
    session.flush()


def _store_tags(session: Session, story: Story, verified: VerifiedStory) -> None:
    written = verified.story
    for kind, values in (
        (TagKind.TOPIC, written.topic_tags),
        (TagKind.ENTITY, written.entity_tags),
    ):
        for value in dict.fromkeys(values):
            session.add(StoryTag(story_id=story.id, kind=kind, value=value[:96], verified=True))


def _store_fact_checks(session: Session, story: Story, verified: VerifiedStory) -> None:
    checked_at = now_utc()
    for finding in verified.findings:
        session.add(
            FactCheck(
                story_id=story.id,
                attempt=verified.attempts,
                claim=f"{finding.element}: {finding.claim}"[:2000],
                verdict=finding.verdict,
                method=finding.method,
                detail=finding.detail or None,
                model=verified.story.model,
                prompt_version=verified.story.prompt_version,
                created_at=checked_at,
            )
        )

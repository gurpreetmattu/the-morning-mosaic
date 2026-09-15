"""Sources, articles, and the verified stories built from them.

The audit chain is deliberate and unbroken:

    article -> article_passages -> sentence_citations -> story_sentences

Every published sentence therefore resolves to the exact passage excerpts that
support it. Cited passages are kept permanently; uncited raw article text is
purged after 30 days.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    CreatedAt,
    EditionDate,
    GenreKeyColumn,
    Instant,
    OptionalInstant,
    UuidPk,
    genre_check,
    pg_enum,
)
from app.models.enums import (
    CheckMethod,
    ClaimVerdict,
    ExtraKind,
    ImageProvider,
    SentenceRole,
    StoryStatus,
    TagKind,
)


class Source(Base):
    """Mirror of an entry in config/sources.yaml, seeded on deploy."""

    __tablename__ = "sources"

    id: Mapped[UuidPk]
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    homepage: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    terms_url: Mapped[str] = mapped_column(Text, nullable=False)
    terms_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[CreatedAt]

    __table_args__ = (
        CheckConstraint("tier IN (1, 2, 3)", name="tier"),
        CheckConstraint("NOT enabled OR terms_confirmed", name="enabled_requires_confirmed_terms"),
    )


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[UuidPk]
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Articles without a reliable published_at are dropped, so this is required.
    published_at: Mapped[Instant]
    fetched_at: Mapped[Instant]
    genre: Mapped[GenreKeyColumn]
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    # Internal processing only, never published, purged after 30 days.
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text_purged_at: Mapped[OptionalInstant]
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[CreatedAt]

    source: Mapped[Source] = relationship()
    passages: Mapped[list[ArticlePassage]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )

    __table_args__ = (
        genre_check("genre", "genre"),
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_content_hash", "content_hash"),
    )


class ArticlePassage(Base):
    """A numbered chunk of extracted text. Citations point here, not at URLs."""

    __tablename__ = "article_passages"

    id: Mapped[UuidPk]
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Set once a published sentence cites this passage: kept permanently.
    cited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[CreatedAt]

    article: Mapped[Article] = relationship(back_populates="passages")

    __table_args__ = (UniqueConstraint("article_id", "ordinal"),)


class StoryCluster(Base):
    """A set of articles reporting the same event."""

    __tablename__ = "story_clusters"

    id: Mapped[UuidPk]
    edition_date: Mapped[EditionDate]
    genre: Mapped[GenreKeyColumn]
    created_at: Mapped[CreatedAt]

    articles: Mapped[list[ClusterArticle]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )

    __table_args__ = (
        genre_check("genre", "genre"),
        Index("ix_story_clusters_edition_date_genre", "edition_date", "genre"),
    )


class ClusterArticle(Base):
    __tablename__ = "cluster_articles"

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("story_clusters.id", ondelete="CASCADE"), primary_key=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    cluster: Mapped[StoryCluster] = relationship(back_populates="articles")
    article: Mapped[Article] = relationship()


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[UuidPk]
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("story_clusters.id", ondelete="RESTRICT"), nullable=False
    )
    edition_date: Mapped[EditionDate]
    genre: Mapped[GenreKeyColumn]
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    one_liner: Mapped[str] = mapped_column(Text, nullable=False)
    # Omitted when the sources give no such context.
    why_this_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True only if a source passage names an Indian entity or place.
    india_relevance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Rank within the genre pool; personalisation reorders in code from here.
    pool_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[StoryStatus] = mapped_column(
        pg_enum(StoryStatus, "story_status"), nullable=False, default=StoryStatus.DRAFT
    )
    hedged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[CreatedAt]

    cluster: Mapped[StoryCluster] = relationship()
    sentences: Mapped[list[StorySentence]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    tags: Mapped[list[StoryTag]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )

    __table_args__ = (
        genre_check("genre", "genre"),
        Index("ix_stories_edition_date_genre", "edition_date", "genre"),
    )


class StorySentence(Base):
    """One published sentence. Its citations are the audit trail."""

    __tablename__ = "story_sentences"

    id: Mapped[UuidPk]
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[SentenceRole] = mapped_column(
        pg_enum(SentenceRole, "sentence_role"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[CreatedAt]

    story: Mapped[Story] = relationship(back_populates="sentences")
    citations: Mapped[list[SentenceCitation]] = relationship(
        back_populates="sentence", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("story_id", "role", "ordinal"),)


class SentenceCitation(Base):
    __tablename__ = "sentence_citations"

    sentence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("story_sentences.id", ondelete="CASCADE"), primary_key=True
    )
    passage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("article_passages.id", ondelete="RESTRICT"), primary_key=True
    )
    # Frozen copy of the passage text as cited, so the audit trail survives
    # any later edit or purge upstream.
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[CreatedAt]

    sentence: Mapped[StorySentence] = relationship(back_populates="citations")
    passage: Mapped[ArticlePassage] = relationship()


class StoryTag(Base):
    __tablename__ = "story_tags"

    id: Mapped[UuidPk]
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[TagKind] = mapped_column(pg_enum(TagKind, "tag_kind"), nullable=False)
    value: Mapped[str] = mapped_column(String(96), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[CreatedAt]

    story: Mapped[Story] = relationship(back_populates="tags")

    __table_args__ = (
        UniqueConstraint("story_id", "kind", "value"),
        Index("ix_story_tags_kind_value", "kind", "value"),
    )


class FactCheck(Base):
    """One atomic claim, checked once. Append-only across retry attempts."""

    __tablename__ = "fact_checks"

    id: Mapped[UuidPk]
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    attempt: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[ClaimVerdict] = mapped_column(
        pg_enum(ClaimVerdict, "claim_verdict"), nullable=False
    )
    method: Mapped[CheckMethod] = mapped_column(
        pg_enum(CheckMethod, "check_method"), nullable=False
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[CreatedAt]

    __table_args__ = (Index("ix_fact_checks_story_id_attempt", "story_id", "attempt"),)


class Correction(Base):
    """A published story found to be wrong. Published content is never edited."""

    __tablename__ = "corrections"

    id: Mapped[UuidPk]
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_at: Mapped[Instant]
    # The edition in which the correction note is shown to affected readers.
    announced_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[CreatedAt]


class StoryWithdrawal(Base):
    """Admin kill switch record."""

    __tablename__ = "story_withdrawals"

    id: Mapped[UuidPk]
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    withdrawn_at: Mapped[Instant]
    created_at: Mapped[CreatedAt]


class Image(Base):
    __tablename__ = "images"

    id: Mapped[UuidPk]
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=True
    )
    provider: Mapped[ImageProvider] = mapped_column(
        pg_enum(ImageProvider, "image_provider"), nullable=False
    )
    # Where the image is displayed from. News photos are hotlinked, never rehosted.
    display_url: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    license_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    credit: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[CreatedAt]


class Extra(Base):
    """Quotes, markets, scores, releases, deals — all from structured sources.

    `source_name` and `source_url` are mandatory: an extra with no attributable
    source is not built at all.
    """

    __tablename__ = "extras"

    id: Mapped[UuidPk]
    edition_date: Mapped[EditionDate]
    kind: Mapped[ExtraKind] = mapped_column(pg_enum(ExtraKind, "extra_kind"), nullable=False)
    genre: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    # The timestamp of the underlying data, shown for market strips.
    data_at: Mapped[Instant]
    created_at: Mapped[CreatedAt]

    __table_args__ = (Index("ix_extras_edition_date_kind", "edition_date", "kind"),)


class WeatherCache(Base):
    __tablename__ = "weather_cache"

    id: Mapped[UuidPk]
    city_id: Mapped[str] = mapped_column(
        ForeignKey("cities.id", ondelete="CASCADE"), nullable=False
    )
    edition_date: Mapped[EditionDate]
    payload: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[Instant]

    __table_args__ = (UniqueConstraint("city_id", "edition_date"),)


__all__ = [
    "Article",
    "ArticlePassage",
    "ClusterArticle",
    "Correction",
    "Extra",
    "FactCheck",
    "Image",
    "SentenceCitation",
    "Source",
    "Story",
    "StoryCluster",
    "StorySentence",
    "StoryTag",
    "StoryWithdrawal",
    "WeatherCache",
]

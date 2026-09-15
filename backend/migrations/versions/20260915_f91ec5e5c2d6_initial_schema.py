"""initial schema

Creates the 32 tables described in CLAUDE.md, "Data model (core tables)".

Revision ID: f91ec5e5c2d6
Revises:
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f91ec5e5c2d6"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cities",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=120), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cities")),
        sa.UniqueConstraint("name", "state", name=op.f("uq_cities_name_state")),
    )
    op.create_table(
        "editions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("edition_date", sa.Date(), nullable=False),
        sa.Column("edition_number", sa.Integer(), nullable=False),
        sa.Column("special_edition_key", sa.String(length=64), nullable=True),
        sa.Column("is_weekend", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("edition_number > 0", name=op.f("ck_editions_edition_number_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_editions")),
        sa.UniqueConstraint("edition_date", name=op.f("uq_editions_edition_date")),
        sa.UniqueConstraint("edition_number", name=op.f("uq_editions_edition_number")),
    )
    op.create_table(
        "extras",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("edition_date", sa.Date(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "quote",
                "on_this_day",
                "market",
                "score",
                "fixture",
                "movie_release",
                "music_release",
                "game_deal",
                "ai_tool",
                "quiz",
                name="extra_kind",
            ),
            nullable=False,
        ),
        sa.Column("genre", sa.String(length=32), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("data_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extras")),
    )
    op.create_index("ix_extras_edition_date_kind", "extras", ["edition_date", "kind"], unique=False)
    op.create_table(
        "notice_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("edition_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "held", "approved", "suppressed", "expired", "sent", name="notice_batch_status"
            ),
            nullable=False,
        ),
        sa.Column("recipient_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(length=320), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "recipient_count >= 0", name=op.f("ck_notice_batches_recipient_count_non_negative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notice_batches")),
        sa.UniqueConstraint("edition_date", name=op.f("uq_notice_batches_edition_date")),
    )
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "job",
            sa.Enum(
                "feedback",
                "build",
                "late_update",
                "delivery",
                "failure_notice",
                "bounces",
                name="job_name",
            ),
            nullable=False,
        ),
        sa.Column("edition_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("running", "succeeded", "failed", "deadline_missed", name="run_status"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_runs")),
    )
    op.create_index(
        "ix_pipeline_runs_job_edition_date", "pipeline_runs", ["job", "edition_date"], unique=False
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("homepage", sa.Text(), nullable=False),
        sa.Column("tier", sa.SmallInteger(), nullable=False),
        sa.Column("terms_url", sa.Text(), nullable=False),
        sa.Column("terms_confirmed", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "NOT enabled OR terms_confirmed",
            name=op.f("ck_sources_enabled_requires_confirmed_terms"),
        ),
        sa.CheckConstraint("tier IN (1, 2, 3)", name=op.f("ck_sources_tier")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
        sa.UniqueConstraint("key", name=op.f("uq_sources_key")),
    )
    op.create_table(
        "story_clusters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("edition_date", sa.Date(), nullable=False),
        sa.Column("genre", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "genre IN ('ai', 'bollywood', 'business', 'gaming', 'hollywood', 'india', 'music', 'politics', 'sports', 'technology')",
            name=op.f("ck_story_clusters_genre"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_story_clusters")),
    )
    op.create_index(
        "ix_story_clusters_edition_date_genre",
        "story_clusters",
        ["edition_date", "genre"],
        unique=False,
    )
    op.create_table(
        "articles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("genre", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("raw_text_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "genre IN ('ai', 'bollywood', 'business', 'gaming', 'hollywood', 'india', 'music', 'politics', 'sports', 'technology')",
            name=op.f("ck_articles_genre"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name=op.f("fk_articles_source_id_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_articles")),
        sa.UniqueConstraint("url", name=op.f("uq_articles_url")),
    )
    op.create_index("ix_articles_content_hash", "articles", ["content_hash"], unique=False)
    op.create_index("ix_articles_published_at", "articles", ["published_at"], unique=False)
    op.create_table(
        "edition_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.SmallInteger(), nullable=False),
        sa.Column(
            "reason",
            sa.Enum("build", "late_update", "withdrawal", name="revision_reason"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_edition_revisions_revision_positive")),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["editions.id"],
            name=op.f("fk_edition_revisions_edition_id_editions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edition_revisions")),
        sa.UniqueConstraint(
            "edition_id", "revision", name=op.f("uq_edition_revisions_edition_id_revision")
        ),
    )
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_run_id", sa.Uuid(), nullable=True),
        sa.Column("agent", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.Enum("ok", "error", name="call_status"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_runs.id"],
            name=op.f("fk_llm_calls_pipeline_run_id_pipeline_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_calls")),
    )
    op.create_index(
        "ix_llm_calls_agent_created_at", "llm_calls", ["agent", "created_at"], unique=False
    )
    op.create_table(
        "stories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cluster_id", sa.Uuid(), nullable=False),
        sa.Column("edition_date", sa.Date(), nullable=False),
        sa.Column("genre", sa.String(length=32), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("one_liner", sa.Text(), nullable=False),
        sa.Column("why_this_matters", sa.Text(), nullable=True),
        sa.Column("india_relevance", sa.Boolean(), nullable=False),
        sa.Column("pool_rank", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "verified", "dropped", "withdrawn", name="story_status"),
            nullable=False,
        ),
        sa.Column("hedged", sa.Boolean(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "genre IN ('ai', 'bollywood', 'business', 'gaming', 'hollywood', 'india', 'music', 'politics', 'sports', 'technology')",
            name=op.f("ck_stories_genre"),
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["story_clusters.id"],
            name=op.f("fk_stories_cluster_id_story_clusters"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stories")),
    )
    op.create_index(
        "ix_stories_edition_date_genre", "stories", ["edition_date", "genre"], unique=False
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("city_id", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "active",
                "paused",
                "unsubscribed",
                "bounced",
                "waitlisted",
                name="subscription_status",
            ),
            nullable=False,
        ),
        sa.Column("delivery_slot", sa.Time(), nullable=False),
        sa.Column("frequency", sa.Enum("daily", "weekdays", name="frequency"), nullable=False),
        sa.Column(
            "edition_preference",
            sa.Enum("india", "global", "mixed", name="edition_preference"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("age_confirmed", sa.Boolean(), nullable=False),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anonymised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "delivery_slot >= TIME '06:00' AND delivery_slot <= TIME '09:00' AND EXTRACT(MINUTE FROM delivery_slot) IN (0, 30) AND EXTRACT(SECOND FROM delivery_slot) = 0",
            name=op.f("ck_users_slot_is_a_half_hour_between_0600_and_0900"),
        ),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        sa.ForeignKeyConstraint(
            ["city_id"], ["cities.id"], name=op.f("fk_users_city_id_cities"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "weather_cache",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.String(length=64), nullable=False),
        sa.Column("edition_date", sa.Date(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["cities.id"],
            name=op.f("fk_weather_cache_city_id_cities"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weather_cache")),
        sa.UniqueConstraint(
            "city_id", "edition_date", name=op.f("uq_weather_cache_city_id_edition_date")
        ),
    )
    op.create_table(
        "article_passages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("cited", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_article_passages_article_id_articles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_article_passages")),
        sa.UniqueConstraint(
            "article_id", "ordinal", name=op.f("uq_article_passages_article_id_ordinal")
        ),
    )
    op.create_table(
        "cluster_articles",
        sa.Column("cluster_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_cluster_articles_article_id_articles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["story_clusters.id"],
            name=op.f("fk_cluster_articles_cluster_id_story_clusters"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("cluster_id", "article_id", name=op.f("pk_cluster_articles")),
    )
    op.create_table(
        "consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_consents_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consents")),
    )
    op.create_table(
        "corrections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("story_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("announced_on", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            ["stories.id"],
            name=op.f("fk_corrections_story_id_stories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_corrections")),
    )
    op.create_table(
        "deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("edition_date", sa.Date(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("newsletter", "failure_notice", "paused_notice", name="delivery_type"),
            nullable=False,
        ),
        sa.Column("revision_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "sending", "sent", "failed", "skipped", name="delivery_status"),
            nullable=False,
        ),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type <> 'newsletter' OR status <> 'sent' OR revision_id IS NOT NULL",
            name=op.f("ck_deliveries_sent_newsletters_record_their_revision"),
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["edition_revisions.id"],
            name=op.f("fk_deliveries_revision_id_edition_revisions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_deliveries_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deliveries")),
        sa.UniqueConstraint(
            "user_id", "edition_date", "type", name=op.f("uq_deliveries_user_id_edition_date_type")
        ),
    )
    op.create_index(
        "ix_deliveries_edition_date_status", "deliveries", ["edition_date", "status"], unique=False
    )
    op.create_table(
        "edition_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("genre", sa.String(length=32), nullable=False),
        sa.Column(
            "status", sa.Enum("ok", "quiet_day", "failed", name="section_status"), nullable=False
        ),
        sa.Column("html", sa.Text(), nullable=True),
        sa.Column("plain_text", sa.Text(), nullable=True),
        sa.Column("pdf_object", sa.Text(), nullable=True),
        sa.Column("story_count", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "genre IN ('ai', 'bollywood', 'business', 'gaming', 'hollywood', 'india', 'music', 'politics', 'sports', 'technology')",
            name=op.f("ck_edition_sections_genre"),
        ),
        sa.CheckConstraint(
            "status <> 'ok' OR (html IS NOT NULL AND plain_text IS NOT NULL)",
            name=op.f("ck_edition_sections_ok_sections_are_rendered"),
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["edition_revisions.id"],
            name=op.f("fk_edition_sections_revision_id_edition_revisions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edition_sections")),
        sa.UniqueConstraint(
            "revision_id", "genre", name=op.f("uq_edition_sections_revision_id_genre")
        ),
    )
    op.create_table(
        "fact_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("story_id", sa.Uuid(), nullable=False),
        sa.Column("attempt", sa.SmallInteger(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column(
            "verdict",
            sa.Enum("supported", "unsupported", "partial", name="claim_verdict"),
            nullable=False,
        ),
        sa.Column("method", sa.Enum("llm", "deterministic", name="check_method"), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            ["stories.id"],
            name=op.f("fk_fact_checks_story_id_stories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fact_checks")),
    )
    op.create_index(
        "ix_fact_checks_story_id_attempt", "fact_checks", ["story_id", "attempt"], unique=False
    )
    op.create_table(
        "feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("story_id", sa.Uuid(), nullable=False),
        sa.Column("vote", sa.Enum("up", "down", name="vote"), nullable=False),
        sa.Column("aggregated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            ["stories.id"],
            name=op.f("fk_feedback_story_id_stories"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_feedback_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback")),
        sa.UniqueConstraint("user_id", "story_id", name=op.f("uq_feedback_user_id_story_id")),
    )
    op.create_index("ix_feedback_aggregated_at", "feedback", ["aggregated_at"], unique=False)
    op.create_table(
        "followed_keywords",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("keyword", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "keyword = lower(keyword)", name=op.f("ck_followed_keywords_keyword_lowercase")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_followed_keywords_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_followed_keywords")),
        sa.UniqueConstraint(
            "user_id", "keyword", name=op.f("uq_followed_keywords_user_id_keyword")
        ),
    )
    op.create_table(
        "images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("story_id", sa.Uuid(), nullable=True),
        sa.Column(
            "provider",
            sa.Enum(
                "wikimedia",
                "unsplash",
                "pexels",
                "publisher",
                "genre_default",
                name="image_provider",
            ),
            nullable=False,
        ),
        sa.Column("display_url", sa.Text(), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("license_name", sa.String(length=120), nullable=True),
        sa.Column("license_url", sa.Text(), nullable=True),
        sa.Column("credit", sa.Text(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            ["stories.id"],
            name=op.f("fk_images_story_id_stories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_images")),
    )
    op.create_table(
        "outage_state",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("consecutive_failed_days", sa.Integer(), nullable=False),
        sa.Column("last_failed_on", sa.Date(), nullable=True),
        sa.Column("paused_notice_sent_on", sa.Date(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_outage_state_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_outage_state")),
    )
    op.create_table(
        "story_sentences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("story_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("headline", "summary", "one_liner", "why_this_matters", name="sentence_role"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            ["stories.id"],
            name=op.f("fk_story_sentences_story_id_stories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_story_sentences")),
        sa.UniqueConstraint(
            "story_id", "role", "ordinal", name=op.f("uq_story_sentences_story_id_role_ordinal")
        ),
    )
    op.create_table(
        "story_tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("story_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Enum("topic", "entity", name="tag_kind"), nullable=False),
        sa.Column("value", sa.String(length=96), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            ["stories.id"],
            name=op.f("fk_story_tags_story_id_stories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_story_tags")),
        sa.UniqueConstraint(
            "story_id", "kind", "value", name=op.f("uq_story_tags_story_id_kind_value")
        ),
    )
    op.create_index("ix_story_tags_kind_value", "story_tags", ["kind", "value"], unique=False)
    op.create_table(
        "story_withdrawals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("story_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            ["stories.id"],
            name=op.f("fk_story_withdrawals_story_id_stories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_story_withdrawals")),
        sa.UniqueConstraint("story_id", name=op.f("uq_story_withdrawals_story_id")),
    )
    op.create_table(
        "tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "purpose",
            sa.Enum("opt_in", "magic_link", "unsubscribe", name="token_purpose"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "expires_at IS NOT NULL OR purpose = 'unsubscribe'",
            name=op.f("ck_tokens_only_unsubscribe_is_permanent"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_tokens_token_hash")),
    )
    op.create_table(
        "user_genres",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("genre", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "genre IN ('ai', 'bollywood', 'business', 'gaming', 'hollywood', 'india', 'music', 'politics', 'sports', 'technology')",
            name=op.f("ck_user_genres_genre"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_genres_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "genre", name=op.f("pk_user_genres")),
    )
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("genre", sa.String(length=32), nullable=False),
        sa.Column("topic_tag", sa.String(length=96), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "genre IN ('ai', 'bollywood', 'business', 'gaming', 'hollywood', 'india', 'music', 'politics', 'sports', 'technology')",
            name=op.f("ck_user_preferences_genre"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_preferences")),
        sa.UniqueConstraint(
            "user_id",
            "genre",
            "topic_tag",
            name=op.f("uq_user_preferences_user_id_genre_topic_tag"),
        ),
    )
    op.create_table(
        "waitlist",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_waitlist_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_waitlist")),
        sa.UniqueConstraint("user_id", name=op.f("uq_waitlist_user_id")),
    )
    op.create_table(
        "sentence_citations",
        sa.Column("sentence_id", sa.Uuid(), nullable=False),
        sa.Column("passage_id", sa.Uuid(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["passage_id"],
            ["article_passages.id"],
            name=op.f("fk_sentence_citations_passage_id_article_passages"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sentence_id"],
            ["story_sentences.id"],
            name=op.f("fk_sentence_citations_sentence_id_story_sentences"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("sentence_id", "passage_id", name=op.f("pk_sentence_citations")),
    )


def downgrade() -> None:
    op.drop_table("sentence_citations")
    op.drop_table("waitlist")
    op.drop_table("user_preferences")
    op.drop_table("user_genres")
    op.drop_table("tokens")
    op.drop_table("story_withdrawals")
    op.drop_index("ix_story_tags_kind_value", table_name="story_tags")
    op.drop_table("story_tags")
    op.drop_table("story_sentences")
    op.drop_table("outage_state")
    op.drop_table("images")
    op.drop_table("followed_keywords")
    op.drop_index("ix_feedback_aggregated_at", table_name="feedback")
    op.drop_table("feedback")
    op.drop_index("ix_fact_checks_story_id_attempt", table_name="fact_checks")
    op.drop_table("fact_checks")
    op.drop_table("edition_sections")
    op.drop_index("ix_deliveries_edition_date_status", table_name="deliveries")
    op.drop_table("deliveries")
    op.drop_table("corrections")
    op.drop_table("consents")
    op.drop_table("cluster_articles")
    op.drop_table("article_passages")
    op.drop_table("weather_cache")
    op.drop_table("users")
    op.drop_index("ix_stories_edition_date_genre", table_name="stories")
    op.drop_table("stories")
    op.drop_index("ix_llm_calls_agent_created_at", table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_table("edition_revisions")
    op.drop_index("ix_articles_content_hash", table_name="articles")
    op.drop_index("ix_articles_published_at", table_name="articles")
    op.drop_table("articles")
    op.drop_index("ix_story_clusters_edition_date_genre", table_name="story_clusters")
    op.drop_table("story_clusters")
    op.drop_table("sources")
    op.drop_index("ix_pipeline_runs_job_edition_date", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
    op.drop_table("notice_batches")
    op.drop_index("ix_extras_edition_date_kind", table_name="extras")
    op.drop_table("extras")
    op.drop_table("editions")
    op.drop_table("cities")

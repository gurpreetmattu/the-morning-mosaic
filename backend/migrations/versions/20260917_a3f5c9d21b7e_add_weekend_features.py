"""add weekend_features

Saturday's "longer reads" and Sunday's "weekly recap" and quiz
(app/render/weekend.py) are built once at build time from stories already
verified earlier in the week. Unlike `extras`, each of these draws on
several of the week's own stories rather than one external source, so the
mandatory `source_name`/`source_url` on `extras` does not fit — hence a
dedicated table rather than a new `extra_kind` member.

Revision ID: a3f5c9d21b7e
Revises: 1972f27b165b
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3f5c9d21b7e"
down_revision: str | None = "1972f27b165b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Native enum type created implicitly by the CREATE TABLE statement below.
ENUM_TYPES: tuple[str, ...] = ("weekend_feature_kind",)


def upgrade() -> None:
    op.create_table(
        "weekend_features",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("edition_date", sa.Date(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("longer_reads", "weekly_recap", "quiz", name="weekend_feature_kind"),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weekend_features")),
        sa.UniqueConstraint(
            "edition_date", "kind", name=op.f("uq_weekend_features_edition_date_kind")
        ),
    )


def downgrade() -> None:
    op.drop_table("weekend_features")
    for enum_name in ENUM_TYPES:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

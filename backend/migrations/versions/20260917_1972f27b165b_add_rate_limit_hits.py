"""add rate_limit_hits

The rate limiter (app/api/security.py) was in-process, so each Cloud Run
instance kept its own counts and the real limit was per instance rather
than global. This table backs an atomic upsert-based fixed-window counter
shared by every instance, keyed by (bucket, key, window_start).

Revision ID: 1972f27b165b
Revises: 424df135328b
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1972f27b165b"
down_revision: str | None = "424df135328b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_hits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bucket", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_hits")),
        sa.UniqueConstraint(
            "bucket", "key", "window_start", name=op.f("uq_rate_limit_hits_bucket_key_window")
        ),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_hits")

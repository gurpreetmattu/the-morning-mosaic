"""add purge to job_name

The 7th scheduled job (raw-article-text retention, CLAUDE.md: "purged
after 30 days") needs its own PipelineRun.job value. Postgres has no
`ALTER TYPE ... DROP VALUE`, so downgrading this leaves the value in
place rather than attempting to rebuild the enum type — harmless, since
nothing downstream fails by a job_name enum simply having an unused member.

Revision ID: 424df135328b
Revises: d5f5dc049b56
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "424df135328b"
down_revision: str | None = "d5f5dc049b56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # IF NOT EXISTS (Postgres 12+) makes this safe to rerun: without it, a
    # downgrade to this migration's own down_revision followed by another
    # upgrade would fail on "value already exists", since downgrade() below
    # cannot actually remove the value.
    op.execute("ALTER TYPE job_name ADD VALUE IF NOT EXISTS 'purge'")


def downgrade() -> None:
    pass

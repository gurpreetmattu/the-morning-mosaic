"""decay preferences by elapsed days not runs

Without a record of when a preference was last decayed, decay is keyed to
how many times the feedback job happened to run rather than to elapsed
calendar days: a day with two runs (a manual rerun) decays a preference
twice, and a day the job never ran does not decay it at all. `last_decayed_at`
lets app/jobs/feedback.py raise the decay to the correct power of elapsed
days instead of always applying it once per call.

Revision ID: d5f5dc049b56
Revises: 6f81cedfa330
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5f5dc049b56"
down_revision: str | None = "6f81cedfa330"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("last_decayed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "last_decayed_at")

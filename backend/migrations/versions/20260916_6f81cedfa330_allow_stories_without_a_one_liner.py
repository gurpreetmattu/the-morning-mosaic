"""allow stories without a one-liner

The one-liner is an optional element: the Fact-checker drops it when it cannot
be verified, and the story is still publishable without it. "Today in 60
seconds" simply omits that story. Requiring the column would force the Writer
to invent a line it could not support.

Revision ID: 6f81cedfa330
Revises: f91ec5e5c2d6
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6f81cedfa330"
down_revision: str | None = "f91ec5e5c2d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("stories", "one_liner", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    # Rows without a one-liner would block the NOT NULL, so give them the
    # headline, which is already verified and cited.
    op.execute("UPDATE stories SET one_liner = headline WHERE one_liner IS NULL")
    op.alter_column("stories", "one_liner", existing_type=sa.Text(), nullable=False)

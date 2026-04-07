"""Make ai_personas.username nullable.

Revision ID: 20260407_01
Revises: 20260407_00
Create Date: 2026-04-07 00:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260407_01"
down_revision: str | Sequence[str] | None = "20260407_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    """Allow ai persona username to be optional."""
    if not _table_exists("ai_personas"):
        return

    op.alter_column(
        "ai_personas",
        "username",
        existing_type=sa.String(length=20),
        nullable=True,
    )


def downgrade() -> None:
    """Revert ai persona username to required."""
    if not _table_exists("ai_personas"):
        return

    op.alter_column(
        "ai_personas",
        "username",
        existing_type=sa.String(length=20),
        nullable=False,
    )

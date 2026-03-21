"""
Revision ID: 20260322_00
Revises: 20260321_03
Create Date: 2026-03-22 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260322_00"
down_revision: str | Sequence[str] | None = "20260321_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    """Ensure square_categories.title length fits contact tag constraints."""
    if not _table_exists("square_categories"):
        return
    op.create_check_constraint(
        "ck_square_categories_title_length",
        "square_categories",
        "char_length(title) <= 20",
    )


def downgrade() -> None:
    """Drop square_categories.title length constraint."""
    if not _table_exists("square_categories"):
        return
    op.drop_constraint(
        "ck_square_categories_title_length",
        "square_categories",
        type_="check",
    )

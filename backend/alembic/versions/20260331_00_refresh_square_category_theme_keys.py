"""Refresh square_categories.theme_key set to direct color names.

Revision ID: 20260331_00
Revises: 20260326_01
Create Date: 2026-03-31 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260331_00"
down_revision: str | Sequence[str] | None = "20260326_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _check_constraint_exists(table_name: str, constraint_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(ck["name"] == constraint_name for ck in inspector.get_check_constraints(table_name))


_NEW_THEME_KEY_CHECK = (
    "theme_key IN ('blue', 'cyan', 'teal', 'green', 'lime', 'yellow', "
    "'orange', 'purple', 'pink', 'magenta', 'beige', 'charcoal')"
)
_OLD_THEME_KEY_CHECK = (
    "theme_key IN ('blue', 'cyan', 'teal', 'green', 'lime', 'yellow', "
    "'amber', 'orange', 'red', 'pink', 'purple', 'gray')"
)


def upgrade() -> None:
    """Migrate theme key values and apply the new key constraint."""
    if not _table_exists("square_categories"):
        return

    if _check_constraint_exists("square_categories", "ck_square_categories_theme_key"):
        op.drop_constraint(
            "ck_square_categories_theme_key",
            "square_categories",
            type_="check",
        )

    op.execute(
        sa.text("UPDATE square_categories SET theme_key = 'orange' WHERE theme_key = 'amber'")
    )
    op.execute(
        sa.text("UPDATE square_categories SET theme_key = 'magenta' WHERE theme_key = 'red'")
    )
    op.execute(
        sa.text("UPDATE square_categories SET theme_key = 'charcoal' WHERE theme_key = 'gray'")
    )

    op.create_check_constraint(
        "ck_square_categories_theme_key",
        "square_categories",
        _NEW_THEME_KEY_CHECK,
    )


def downgrade() -> None:
    """Restore the previous theme key constraint and compatible key values."""
    if not _table_exists("square_categories"):
        return

    if _check_constraint_exists("square_categories", "ck_square_categories_theme_key"):
        op.drop_constraint(
            "ck_square_categories_theme_key",
            "square_categories",
            type_="check",
        )

    op.execute(
        sa.text("UPDATE square_categories SET theme_key = 'red' WHERE theme_key = 'magenta'")
    )
    op.execute(
        sa.text(
            "UPDATE square_categories SET theme_key = 'gray' "
            "WHERE theme_key IN ('beige', 'charcoal')"
        )
    )

    op.create_check_constraint(
        "ck_square_categories_theme_key",
        "square_categories",
        _OLD_THEME_KEY_CHECK,
    )

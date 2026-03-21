"""Refactor square_categories.theme_key to plain color words.

Revision ID: 20260321_01
Revises: 20260321_00
Create Date: 2026-03-21 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260321_01"
down_revision: str | Sequence[str] | None = "20260321_00"
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
    "'amber', 'orange', 'red', 'pink', 'purple', 'gray')"
)
_OLD_THEME_KEY_CHECK = (
    "theme_key IN ('ocean', 'sky', 'mint', 'forest', 'lime', 'amber', "
    "'sunset', 'rose', 'grape', 'slate')"
)


def upgrade() -> None:
    """Migrate theme_key values and update the check constraint."""
    if not _table_exists("square_categories"):
        return

    if _check_constraint_exists("square_categories", "ck_square_categories_theme_key"):
        op.drop_constraint(
            "ck_square_categories_theme_key",
            "square_categories",
            type_="check",
        )

    op.execute(sa.text("UPDATE square_categories SET theme_key = 'blue' WHERE theme_key = 'ocean'"))
    op.execute(sa.text("UPDATE square_categories SET theme_key = 'cyan' WHERE theme_key = 'sky'"))
    op.execute(sa.text("UPDATE square_categories SET theme_key = 'teal' WHERE theme_key = 'mint'"))
    op.execute(
        sa.text("UPDATE square_categories SET theme_key = 'green' WHERE theme_key = 'forest'")
    )
    op.execute(
        sa.text("UPDATE square_categories SET theme_key = 'orange' WHERE theme_key = 'sunset'")
    )
    op.execute(sa.text("UPDATE square_categories SET theme_key = 'pink' WHERE theme_key = 'rose'"))
    op.execute(
        sa.text("UPDATE square_categories SET theme_key = 'purple' WHERE theme_key = 'grape'")
    )
    op.execute(sa.text("UPDATE square_categories SET theme_key = 'gray' WHERE theme_key = 'slate'"))

    op.create_check_constraint(
        "ck_square_categories_theme_key",
        "square_categories",
        _NEW_THEME_KEY_CHECK,
    )


def downgrade() -> None:
    """Revert theme_key values and restore the original check constraint."""
    if not _table_exists("square_categories"):
        return

    bind = op.get_bind()
    result = bind.execute(
        sa.text("SELECT COUNT(1) FROM square_categories WHERE theme_key IN ('yellow', 'red')")
    )
    count = int(result.scalar() or 0)
    if count > 0:
        raise RuntimeError("Cannot downgrade square_categories.theme_key: yellow/red are present")

    if _check_constraint_exists("square_categories", "ck_square_categories_theme_key"):
        op.drop_constraint(
            "ck_square_categories_theme_key",
            "square_categories",
            type_="check",
        )

    op.execute(sa.text("UPDATE square_categories SET theme_key = 'ocean' WHERE theme_key = 'blue'"))
    op.execute(sa.text("UPDATE square_categories SET theme_key = 'sky' WHERE theme_key = 'cyan'"))
    op.execute(sa.text("UPDATE square_categories SET theme_key = 'mint' WHERE theme_key = 'teal'"))
    op.execute(
        sa.text("UPDATE square_categories SET theme_key = 'forest' WHERE theme_key = 'green'")
    )
    op.execute(
        sa.text("UPDATE square_categories SET theme_key = 'sunset' WHERE theme_key = 'orange'")
    )
    op.execute(sa.text("UPDATE square_categories SET theme_key = 'rose' WHERE theme_key = 'pink'"))
    op.execute(
        sa.text("UPDATE square_categories SET theme_key = 'grape' WHERE theme_key = 'purple'")
    )
    op.execute(sa.text("UPDATE square_categories SET theme_key = 'slate' WHERE theme_key = 'gray'"))

    op.create_check_constraint(
        "ck_square_categories_theme_key",
        "square_categories",
        _OLD_THEME_KEY_CHECK,
    )

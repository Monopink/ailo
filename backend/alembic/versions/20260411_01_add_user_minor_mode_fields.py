"""Add minor mode fields to users table.

Revision ID: 20260411_01
Revises: 20260411_00
Create Date: 2026-04-11 12:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260411_01"
down_revision: str | Sequence[str] | None = "20260411_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    """Add minor mode status and PIN columns for users."""
    if not _table_exists("users"):
        return

    if not _column_exists("users", "minor_mode_enabled"):
        op.add_column(
            "users",
            sa.Column(
                "minor_mode_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
                comment="Whether minor mode is enabled",
            ),
        )

    if not _column_exists("users", "minor_mode_pin_hash"):
        op.add_column(
            "users",
            sa.Column(
                "minor_mode_pin_hash",
                sa.String(length=255),
                nullable=True,
                comment="Minor mode PIN hash",
            ),
        )

    if not _column_exists("users", "minor_mode_enabled_at"):
        op.add_column(
            "users",
            sa.Column(
                "minor_mode_enabled_at",
                sa.TIMESTAMP(timezone=True),
                nullable=True,
                comment="Minor mode enable timestamp",
            ),
        )

    if not _column_exists("users", "minor_mode_disabled_at"):
        op.add_column(
            "users",
            sa.Column(
                "minor_mode_disabled_at",
                sa.TIMESTAMP(timezone=True),
                nullable=True,
                comment="Minor mode disable timestamp",
            ),
        )

    if not _column_exists("users", "minor_mode_pin_updated_at"):
        op.add_column(
            "users",
            sa.Column(
                "minor_mode_pin_updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=True,
                comment="Minor mode PIN last update timestamp",
            ),
        )


def downgrade() -> None:
    """Remove minor mode columns from users."""
    if not _table_exists("users"):
        return

    if _column_exists("users", "minor_mode_pin_updated_at"):
        op.drop_column("users", "minor_mode_pin_updated_at")
    if _column_exists("users", "minor_mode_disabled_at"):
        op.drop_column("users", "minor_mode_disabled_at")
    if _column_exists("users", "minor_mode_enabled_at"):
        op.drop_column("users", "minor_mode_enabled_at")
    if _column_exists("users", "minor_mode_pin_hash"):
        op.drop_column("users", "minor_mode_pin_hash")
    if _column_exists("users", "minor_mode_enabled"):
        op.drop_column("users", "minor_mode_enabled")

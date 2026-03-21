"""Add ai_personas tags/remark for contact presets.

Revision ID: 20260321_00
Revises: 20260320_02
Create Date: 2026-03-21 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260321_00"
down_revision: str | Sequence[str] | None = "20260320_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    """Upgrade schema to support persona contact preset fields."""

    if not _table_exists("ai_personas"):
        return

    if not _column_exists("ai_personas", "tags"):
        op.add_column("ai_personas", sa.Column("tags", postgresql.JSONB(), nullable=True))
        op.execute(
            "COMMENT ON COLUMN ai_personas.tags IS 'Preset contact tags written into contacts.tags on add'"
        )

    if not _column_exists("ai_personas", "remark"):
        op.add_column("ai_personas", sa.Column("remark", sa.Text(), nullable=True))
        op.execute(
            "COMMENT ON COLUMN ai_personas.remark IS 'Preset contact remark written into contacts.remark on add'"
        )


def downgrade() -> None:
    """Downgrade schema."""

    if not _table_exists("ai_personas"):
        return

    if _column_exists("ai_personas", "remark"):
        op.drop_column("ai_personas", "remark")

    if _column_exists("ai_personas", "tags"):
        op.drop_column("ai_personas", "tags")

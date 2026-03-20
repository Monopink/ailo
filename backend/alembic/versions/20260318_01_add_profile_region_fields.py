"""Add profile region fields.

Revision ID: 20260318_01
Revises: fe62a5fa91e3
Create Date: 2026-03-18 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260318_01"
down_revision: str = "fe62a5fa91e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_profile_columns() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns("profiles")}


def upgrade() -> None:
    """Add region columns to profiles when missing."""
    profile_columns = _get_profile_columns()
    if "region_country_code" not in profile_columns:
        op.add_column(
            "profiles",
            sa.Column("region_country_code", sa.String(length=2), nullable=True),
        )
    if "region_cn_city_code" not in profile_columns:
        op.add_column(
            "profiles",
            sa.Column("region_cn_city_code", sa.String(length=6), nullable=True),
        )


def downgrade() -> None:
    """Remove region columns from profiles when present."""
    profile_columns = _get_profile_columns()
    if "region_cn_city_code" in profile_columns:
        op.drop_column("profiles", "region_cn_city_code")
    if "region_country_code" in profile_columns:
        op.drop_column("profiles", "region_country_code")

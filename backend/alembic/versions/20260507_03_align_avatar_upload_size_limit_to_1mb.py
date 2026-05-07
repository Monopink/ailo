"""Align avatar upload size limit to 1MB.

Revision ID: 20260507_03
Revises: 20260507_02
Create Date: 2026-05-07 19:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260507_03"
down_revision: str | Sequence[str] | None = "20260507_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Set avatar max upload size to 1MB."""
    op.execute(
        """
        UPDATE system_configs
        SET config_value = to_jsonb(1::bigint),
            default_value = to_jsonb(1::bigint)
        WHERE config_key = 'avatar_max_size_mb'
        """
    )


def downgrade() -> None:
    """Restore avatar max upload size to 2MB."""
    op.execute(
        """
        UPDATE system_configs
        SET config_value = to_jsonb(2::bigint),
            default_value = to_jsonb(2::bigint)
        WHERE config_key = 'avatar_max_size_mb'
        """
    )

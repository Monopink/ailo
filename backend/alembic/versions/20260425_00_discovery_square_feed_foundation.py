"""Prepare discovery square schema for multi-category feed.

Revision ID: 20260425_00
Revises: 20260412_00
Create Date: 2026-04-25 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260425_00"
down_revision: str | Sequence[str] | None = "20260412_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop active type uniqueness and add discovery feed indexes."""

    op.drop_index("uq_square_type_entries_active_type_id", table_name="square_type_entries")

    op.create_index(
        "idx_square_type_entries_category_status_type",
        "square_type_entries",
        ["category_key", "status", "type_id"],
        unique=False,
    )
    op.create_index(
        "idx_ai_personas_type_status_qiao",
        "ai_personas",
        ["type_id", "status", "qiao_id"],
        unique=False,
    )
    op.create_index(
        "idx_contacts_user_type_qiao",
        "contacts",
        ["user_qiao_id", "contact_type", "contact_qiao_id"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO system_configs (
            config_key,
            config_value,
            default_value,
            config_type,
            description,
            group_name,
            allowed_values
        )
        VALUES
            (
                'square_refresh_rate_limit_requests',
                '1',
                '1',
                2,
                'Square feed refresh requests per window',
                'discovery_square',
                NULL
            ),
            (
                'square_refresh_rate_limit_window_seconds',
                '10',
                '10',
                2,
                'Square feed refresh window in seconds',
                'discovery_square',
                NULL
            ),
            (
                'square_load_more_rate_limit_requests',
                '3',
                '3',
                2,
                'Square feed load-more requests per window',
                'discovery_square',
                NULL
            ),
            (
                'square_load_more_rate_limit_window_seconds',
                '1',
                '1',
                2,
                'Square feed load-more window in seconds',
                'discovery_square',
                NULL
            )
        ON CONFLICT (config_key) DO NOTHING
        """
    )


def downgrade() -> None:
    """Restore previous unique constraint and remove added indexes."""

    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'square_refresh_rate_limit_requests',
            'square_refresh_rate_limit_window_seconds',
            'square_load_more_rate_limit_requests',
            'square_load_more_rate_limit_window_seconds'
        )
        """
    )
    op.drop_index("idx_contacts_user_type_qiao", table_name="contacts")
    op.drop_index("idx_ai_personas_type_status_qiao", table_name="ai_personas")
    op.drop_index(
        "idx_square_type_entries_category_status_type",
        table_name="square_type_entries",
    )
    op.create_index(
        "uq_square_type_entries_active_type_id",
        "square_type_entries",
        ["type_id"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )

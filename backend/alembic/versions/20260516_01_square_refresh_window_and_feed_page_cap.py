"""Add square refresh window state and feed page cap configs.

Revision ID: 20260516_01
Revises: 20260510_02
Create Date: 2026-05-16 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260516_01"
down_revision: str | Sequence[str] | None = "20260510_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create state table and seed refresh-window configs."""

    op.create_table(
        "square_user_category_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("user_qiao_id", sa.String(length=32), nullable=False, comment="Owner qiao_id"),
        sa.Column("category_key", sa.String(length=64), nullable=False, comment="Category key"),
        sa.Column("feed_version", sa.String(length=32), nullable=False, comment="Feed version"),
        sa.Column(
            "last_refreshed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            comment="Last feed refresh timestamp",
        ),
        sa.Column(
            "next_refresh_available_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            comment="Next allowed refresh timestamp",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="Record last update timestamp",
        ),
        sa.ForeignKeyConstraint(
            ["category_key"],
            ["square_categories.category_key"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_qiao_id",
            "category_key",
            name="uq_square_user_category_state_user_category",
        ),
    )
    op.create_index(
        "idx_square_user_category_state_user_category",
        "square_user_category_state",
        ["user_qiao_id", "category_key"],
        unique=False,
    )
    op.create_index(
        "idx_square_user_category_state_next_refresh",
        "square_user_category_state",
        ["next_refresh_available_at"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO system_configs (
            config_key,
            config_value,
            default_value,
            value_type,
            config_shape,
            config_scope,
            description,
            group_name,
            allowed_values
        )
        VALUES
            (
                'square_refresh_interval_seconds',
                '7200',
                '7200',
                2,
                1,
                'system',
                'Square feed refresh interval in seconds per user and category',
                'discovery_square',
                NULL
            ),
            (
                'square_max_pages_per_feed',
                '3',
                '3',
                2,
                1,
                'system',
                'Square max page count per feed version',
                'discovery_square',
                NULL
            )
        ON CONFLICT (config_key) DO NOTHING
        """
    )

    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'square_rate_limit_requests',
            'square_rate_limit_window_seconds'
        )
        """
    )


def downgrade() -> None:
    """Drop state table and restore removed legacy configs."""

    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'square_refresh_interval_seconds',
            'square_max_pages_per_feed'
        )
        """
    )

    op.execute(
        """
        INSERT INTO system_configs (
            config_key,
            config_value,
            default_value,
            value_type,
            config_shape,
            config_scope,
            description,
            group_name,
            allowed_values
        )
        VALUES
            (
                'square_rate_limit_requests',
                '1',
                '1',
                2,
                1,
                'system',
                'Square refresh requests per window',
                'discovery_square',
                NULL
            ),
            (
                'square_rate_limit_window_seconds',
                '10',
                '10',
                2,
                1,
                'system',
                'Square refresh window in seconds',
                'discovery_square',
                NULL
            )
        ON CONFLICT (config_key) DO NOTHING
        """
    )

    op.drop_index(
        "idx_square_user_category_state_next_refresh",
        table_name="square_user_category_state",
    )
    op.drop_index(
        "idx_square_user_category_state_user_category",
        table_name="square_user_category_state",
    )
    op.drop_table("square_user_category_state")

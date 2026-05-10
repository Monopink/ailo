"""Add redeem batch user counters for atomic per-user claim caps.

Revision ID: 20260510_02
Revises: 20260510_01
Create Date: 2026-05-10 22:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260510_02"
down_revision: str | Sequence[str] | None = "20260510_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create counter table and backfill from redeem_code_claims."""
    op.create_table(
        "redeem_batch_user_counters",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column(
            "batch_id",
            sa.Integer(),
            sa.ForeignKey("redeem_code_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claimed_total", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Record last update timestamp",
        ),
        sa.CheckConstraint(
            "claimed_total >= 0",
            name="ck_redeem_batch_user_counters_claimed_total_nonnegative",
        ),
        sa.UniqueConstraint("batch_id", "user_id", name="uq_redeem_batch_user_counters_batch_user"),
    )
    op.create_index(
        "idx_redeem_batch_user_counters_user_time",
        "redeem_batch_user_counters",
        ["user_id", "updated_at"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO redeem_batch_user_counters (
            batch_id,
            user_id,
            claimed_total,
            created_at,
            updated_at
        )
        SELECT
            batch_id,
            user_id,
            COUNT(*)::bigint AS claimed_total,
            NOW() AS created_at,
            NOW() AS updated_at
        FROM redeem_code_claims
        GROUP BY batch_id, user_id
        ON CONFLICT (batch_id, user_id) DO UPDATE
        SET claimed_total = EXCLUDED.claimed_total,
            updated_at = NOW()
        """
    )


def downgrade() -> None:
    """Drop counter table."""
    op.drop_index(
        "idx_redeem_batch_user_counters_user_time",
        table_name="redeem_batch_user_counters",
    )
    op.drop_table("redeem_batch_user_counters")

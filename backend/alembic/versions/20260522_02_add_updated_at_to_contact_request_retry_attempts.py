"""Add updated_at column to contact_request_retry_attempts.

Revision ID: 20260522_02
Revises: 20260522_01
Create Date: 2026-05-22 23:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260522_02"
down_revision: str | Sequence[str] | None = "20260522_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add updated_at required by SnowflakeModel inheritance."""
    op.add_column(
        "contact_request_retry_attempts",
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Record last update timestamp",
        ),
    )


def downgrade() -> None:
    """Drop updated_at column."""
    op.drop_column("contact_request_retry_attempts", "updated_at")

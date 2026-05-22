"""Add selected_ai_type_id to contact_request_retry_attempts.

Revision ID: 20260522_03
Revises: 20260522_02
Create Date: 2026-05-22 23:59:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260522_03"
down_revision: str | Sequence[str] | None = "20260522_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add manual selected AI type and normalize mode value."""
    op.add_column(
        "contact_request_retry_attempts",
        sa.Column(
            "selected_ai_type_id",
            sa.Integer(),
            nullable=True,
            comment="Selected ai_types.id when mode=MANUAL",
        ),
    )
    op.execute(
        "UPDATE contact_request_retry_attempts SET mode = 'MANUAL' WHERE mode = 'TEMPLATE'"
    )


def downgrade() -> None:
    """Remove selected_ai_type_id and revert mode value."""
    op.execute("UPDATE contact_request_retry_attempts SET mode = 'TEMPLATE' WHERE mode = 'MANUAL'")
    op.drop_column("contact_request_retry_attempts", "selected_ai_type_id")

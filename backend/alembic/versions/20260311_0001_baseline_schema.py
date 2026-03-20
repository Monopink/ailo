"""Baseline schema revision after migration reset.

Revision ID: 20260311_0001
Revises:
Create Date: 2026-03-11 10:05:00
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260311_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""

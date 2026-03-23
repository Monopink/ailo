"""
Revision ID: 20260323_00
Revises: 20260322_00
Create Date: 2026-03-23 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260323_00"
down_revision: str | Sequence[str] | None = "20260322_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    """Normalize ai_message_buffer.last_message_category persisted values."""
    if not _table_exists("ai_message_buffer"):
        return

    op.execute(
        sa.text(
            """
            UPDATE ai_message_buffer
            SET last_message_category = :new_value
            WHERE last_message_category = :old_value
            """
        ).bindparams(old_value="CONTENT_TYPING", new_value="content_typing")
    )
    op.execute(
        sa.text(
            """
            UPDATE ai_message_buffer
            SET last_message_category = :new_value
            WHERE last_message_category = :old_value
            """
        ).bindparams(old_value="CONTENT_NO_TYPING", new_value="content_no_typing")
    )


def downgrade() -> None:
    """Restore legacy ai_message_buffer.last_message_category values."""
    if not _table_exists("ai_message_buffer"):
        return

    op.execute(
        sa.text(
            """
            UPDATE ai_message_buffer
            SET last_message_category = :new_value
            WHERE last_message_category = :old_value
            """
        ).bindparams(old_value="content_typing", new_value="CONTENT_TYPING")
    )
    op.execute(
        sa.text(
            """
            UPDATE ai_message_buffer
            SET last_message_category = :new_value
            WHERE last_message_category = :old_value
            """
        ).bindparams(old_value="content_no_typing", new_value="CONTENT_NO_TYPING")
    )

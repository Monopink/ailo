"""
Revision ID: 20260321_03
Revises: 20260321_02
Create Date: 2026-03-21 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260321_03"
down_revision: str | Sequence[str] | None = "20260321_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    """Remove sms_code_length_digits config key (migrated to code constant)."""
    if not _table_exists("system_configs"):
        return
    op.execute(
        sa.text(
            """
            DELETE FROM system_configs
            WHERE config_key = 'sms_code_length_digits'
            """
        )
    )


def downgrade() -> None:
    """Restore sms_code_length_digits system config row."""
    if not _table_exists("system_configs"):
        return
    op.execute(
        sa.text(
            """
            INSERT INTO system_configs (
                config_key,
                config_value,
                default_value,
                config_type,
                description,
                group_name,
                allowed_values
            ) VALUES (
                'sms_code_length_digits',
                '6',
                '6',
                2,
                'SMS code length in digits',
                'sms',
                NULL
            )
            ON CONFLICT (config_key) DO NOTHING
            """
        )
    )

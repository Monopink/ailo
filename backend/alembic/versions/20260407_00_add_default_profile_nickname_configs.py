"""Add default profile nickname system configs.

Revision ID: 20260407_00
Revises: 20260331_00
Create Date: 2026-04-07 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260407_00"
down_revision: str | Sequence[str] | None = "20260331_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    """Insert default profile nickname config keys."""
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
            ) VALUES
            (
                'default_nickname_prefix',
                '无名敲客_',
                '无名敲客_',
                1,
                'Default prefix for system-generated profile nickname',
                'profile',
                NULL
            ),
            (
                'default_nickname_suffix_length',
                '6',
                '6',
                2,
                'Random uppercase suffix length for system-generated profile nickname (>=1)',
                'profile',
                NULL
            )
            ON CONFLICT (config_key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    """Remove default profile nickname config keys."""
    if not _table_exists("system_configs"):
        return

    op.execute(
        sa.text(
            """
            DELETE FROM system_configs
            WHERE config_key IN ('default_nickname_prefix', 'default_nickname_suffix_length')
            """
        )
    )

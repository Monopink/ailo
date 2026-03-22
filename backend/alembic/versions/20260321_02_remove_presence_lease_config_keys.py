"""
Revision ID: 20260321_02
Revises: 20260321_01
Create Date: 2026-03-21 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260321_02"
down_revision: str | Sequence[str] | None = "20260321_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CONFIG_KEYS = ("ws_presence_lease_ttl_seconds", "registration_lease_ttl_days")


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    """Remove non-operational lease TTL config keys from system_configs."""
    if not _table_exists("system_configs"):
        return

    op.execute(
        sa.text(
            """
            DELETE FROM system_configs
            WHERE config_key IN ('ws_presence_lease_ttl_seconds', 'registration_lease_ttl_days')
            """
        )
    )


def downgrade() -> None:
    """Restore removed system_configs rows."""
    if not _table_exists("system_configs"):
        return

    bind = op.get_bind()
    bind.execute(
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
                ('ws_presence_lease_ttl_seconds', '90', '90', 2, 'WebSocket presence lease TTL in seconds', 'message_transport', NULL),
                ('registration_lease_ttl_days', '365', '365', 2, 'Registration lease TTL in days (e.g., LeanCloud installation binding)', 'message_transport', NULL)
            ON CONFLICT (config_key) DO NOTHING
            """
        )
    )

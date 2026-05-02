"""Add mp_weixin review mode system config.

Revision ID: 20260502_02
Revises: 20260502_01
Create Date: 2026-05-02 18:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260502_02"
down_revision: str | Sequence[str] | None = "20260502_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the unauthenticated mp_weixin review mode switch."""
    op.execute(
        """
        INSERT INTO system_configs (
            config_key,
            config_value,
            default_value,
            value_type,
            config_shape,
            description,
            group_name,
            config_scope,
            allowed_values
        )
        VALUES (
            'mp_weixin_review_mode',
            'false'::jsonb,
            'false'::jsonb,
            3,
            1,
            'Enable review routing override for unauthenticated mp_weixin preflight probes',
            'review',
            'security',
            NULL
        )
        ON CONFLICT (config_key) DO UPDATE
        SET
            config_value = EXCLUDED.config_value,
            default_value = EXCLUDED.default_value,
            value_type = EXCLUDED.value_type,
            config_shape = EXCLUDED.config_shape,
            description = EXCLUDED.description,
            group_name = EXCLUDED.group_name,
            config_scope = EXCLUDED.config_scope,
            allowed_values = EXCLUDED.allowed_values,
            updated_at = NOW()
        """
    )


def downgrade() -> None:
    """Remove the mp_weixin review mode switch."""
    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key = 'mp_weixin_review_mode'
        """
    )

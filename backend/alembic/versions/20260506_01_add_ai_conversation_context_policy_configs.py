"""Add AI conversation context policy configs.

Revision ID: 20260506_01
Revises: 20260505_01
Create Date: 2026-05-06 16:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260506_01"
down_revision: str | Sequence[str] | None = "20260505_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add AI conversation context policy configs."""
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
                'ai_conversation_context_max_messages',
                '20'::jsonb,
                '20'::jsonb,
                2,
                1,
                'system',
                'AI conversation context message limit',
                'ai_conversation',
                NULL
            ),
            (
                'ai_conversation_context_time_window_days',
                '30'::jsonb,
                '30'::jsonb,
                2,
                1,
                'system',
                'AI conversation context time window in days',
                'ai_conversation',
                NULL
            )
        ON CONFLICT (config_key) DO UPDATE
        SET
            config_value = EXCLUDED.config_value,
            default_value = EXCLUDED.default_value,
            value_type = EXCLUDED.value_type,
            config_shape = EXCLUDED.config_shape,
            config_scope = EXCLUDED.config_scope,
            description = EXCLUDED.description,
            group_name = EXCLUDED.group_name,
            allowed_values = EXCLUDED.allowed_values,
            updated_at = NOW()
        """
    )


def downgrade() -> None:
    """Remove AI conversation context policy configs."""
    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'ai_conversation_context_max_messages',
            'ai_conversation_context_time_window_days'
        )
        """
    )

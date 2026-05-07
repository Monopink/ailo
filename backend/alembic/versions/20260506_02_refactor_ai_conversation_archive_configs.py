"""Refactor AI conversation archive system_configs keys.

Revision ID: 20260506_02
Revises: 20260506_01
Create Date: 2026-05-06 18:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260506_02"
down_revision: str | Sequence[str] | None = "20260506_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace legacy archive config keys with retention-based policy keys."""
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
                'ai_conversation_archive_enabled',
                'true'::jsonb,
                'true'::jsonb,
                3,
                1,
                'system',
                'Enable AI conversation items archive job',
                'ai_conversation',
                NULL
            ),
            (
                'ai_conversation_archive_retention_days',
                '14'::jsonb,
                '14'::jsonb,
                2,
                1,
                'system',
                'Archive AI conversation items older than this many days',
                'ai_conversation',
                NULL
            ),
            (
                'ai_conversation_archive_keep_recent_count',
                '200'::jsonb,
                '200'::jsonb,
                2,
                1,
                'system',
                'Per conversation, keep this many recent items in hot table',
                'ai_conversation',
                NULL
            ),
            (
                'ai_conversation_archive_batch_size',
                '1000'::jsonb,
                '1000'::jsonb,
                2,
                1,
                'system',
                'Maximum items archived per archive job round',
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

    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'ai_conversation_archive_time_days',
            'ai_conversation_archive_max_count',
            'ai_conversation_archive_min_count',
            'ai_conversation_archive_threshold'
        )
        """
    )


def downgrade() -> None:
    """Restore legacy archive config keys and remove retention-policy keys."""
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
                'ai_conversation_archive_time_days',
                '7'::jsonb,
                '7'::jsonb,
                2,
                1,
                'system',
                'Archive AI conversation items older than this many days',
                'ai_conversation',
                NULL
            ),
            (
                'ai_conversation_archive_max_count',
                '50'::jsonb,
                '50'::jsonb,
                2,
                1,
                'system',
                'Archive AI conversation items when count exceeds this limit',
                'ai_conversation',
                NULL
            ),
            (
                'ai_conversation_archive_min_count',
                '10'::jsonb,
                '10'::jsonb,
                2,
                1,
                'system',
                'Minimum AI conversation items to keep; do not archive if below this count',
                'ai_conversation',
                NULL
            ),
            (
                'ai_conversation_archive_threshold',
                '80'::jsonb,
                '80'::jsonb,
                2,
                1,
                'system',
                'Trigger immediate archive when AI conversation items exceed this threshold',
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

    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'ai_conversation_archive_enabled',
            'ai_conversation_archive_retention_days',
            'ai_conversation_archive_keep_recent_count',
            'ai_conversation_archive_batch_size'
        )
        """
    )

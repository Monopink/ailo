"""Refactor mp_weixin reviewer detection configs to build-cycle model.

Revision ID: 20260502_04
Revises: 20260502_03
Create Date: 2026-05-02 23:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260502_04"
down_revision: str | Sequence[str] | None = "20260502_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace legacy review-mode switch with build-cycle review configs."""
    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key = 'mp_weixin_review_mode'
        """
    )

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
                'mp_weixin_review_deadline_at',
                'null'::jsonb,
                'null'::jsonb,
                6,
                1,
                'system',
                'UTC deadline for mp_weixin review cycle; null or expired means non-review period',
                'review',
                NULL
            ),
            (
                'mp_weixin_review_build_ids',
                '[]'::jsonb,
                '[]'::jsonb,
                1,
                2,
                'system',
                'Build IDs used for mp_weixin reviewer detection',
                'review',
                NULL
            ),
            (
                'mp_weixin_review_build_time_from',
                'null'::jsonb,
                'null'::jsonb,
                6,
                1,
                'system',
                'Lower UTC bound for mp_weixin reviewer build time matching',
                'review',
                NULL
            ),
            (
                'mp_weixin_review_build_time_to',
                'null'::jsonb,
                'null'::jsonb,
                6,
                1,
                'system',
                'Upper UTC bound for mp_weixin reviewer build time matching',
                'review',
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
    """Restore legacy mp_weixin review mode switch."""
    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'mp_weixin_review_deadline_at',
            'mp_weixin_review_build_ids',
            'mp_weixin_review_build_time_from',
            'mp_weixin_review_build_time_to'
        )
        """
    )

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
        VALUES (
            'mp_weixin_review_mode',
            'false'::jsonb,
            'false'::jsonb,
            3,
            1,
            'system',
            'Enable review routing override for unauthenticated mp_weixin preflight probes',
            'review',
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

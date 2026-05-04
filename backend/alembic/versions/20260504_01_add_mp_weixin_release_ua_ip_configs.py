"""Add mp_weixin reviewer detection configs for release build UA and review IP.

Revision ID: 20260504_01
Revises: 20260503_01
Create Date: 2026-05-04 13:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260504_01"
down_revision: str | Sequence[str] | None = "20260503_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add release-build and review-IP config keys for reviewer detection."""
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
                'mp_weixin_release_build_ids',
                '[]'::jsonb,
                '[]'::jsonb,
                1,
                2,
                'system',
                'Release build IDs used for mp_weixin simulator reviewer detection',
                'review',
                NULL
            ),
            (
                'mp_weixin_review_ip_blacklist',
                '[]'::jsonb,
                '[]'::jsonb,
                1,
                2,
                'system',
                'Reviewer IP blacklist for mp_weixin reviewer detection',
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
    """Remove release-build and review-IP reviewer-detection config keys."""
    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'mp_weixin_release_build_ids',
            'mp_weixin_review_ip_blacklist'
        )
        """
    )

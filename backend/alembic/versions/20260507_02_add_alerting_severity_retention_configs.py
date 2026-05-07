"""Add alerting severity-based retention configs.

Revision ID: 20260507_02
Revises: 20260507_01
Create Date: 2026-05-07 21:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260507_02"
down_revision: str | Sequence[str] | None = "20260507_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Insert severity-level retention configs for alert cleanup."""
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
                'alerting_retention_days_debug',
                '7'::jsonb,
                '7'::jsonb,
                2,
                1,
                'system',
                'Retention days for DEBUG (10) alert_events',
                'alerting',
                NULL
            ),
            (
                'alerting_retention_days_info',
                '14'::jsonb,
                '14'::jsonb,
                2,
                1,
                'system',
                'Retention days for INFO (20) alert_events',
                'alerting',
                NULL
            ),
            (
                'alerting_retention_days_warning',
                '30'::jsonb,
                '30'::jsonb,
                2,
                1,
                'system',
                'Retention days for WARNING (30) alert_events',
                'alerting',
                NULL
            ),
            (
                'alerting_retention_days_error',
                '90'::jsonb,
                '90'::jsonb,
                2,
                1,
                'system',
                'Retention days for ERROR (40) alert_events',
                'alerting',
                NULL
            ),
            (
                'alerting_retention_days_critical',
                '180'::jsonb,
                '180'::jsonb,
                2,
                1,
                'system',
                'Retention days for CRITICAL (50) alert_events',
                'alerting',
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
    """Remove severity-level retention configs for alert cleanup."""
    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'alerting_retention_days_debug',
            'alerting_retention_days_info',
            'alerting_retention_days_warning',
            'alerting_retention_days_error',
            'alerting_retention_days_critical'
        )
        """
    )

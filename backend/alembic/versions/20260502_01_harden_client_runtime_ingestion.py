"""Harden runtime/public intake ingestion and add runtime client IP.

Revision ID: 20260502_01
Revises: 20260501_02
Create Date: 2026-05-02 18:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260502_01"
down_revision: str | Sequence[str] | None = "20260501_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add safety constraints and rate-limit config keys for client ingestion paths."""
    op.execute(
        """
        ALTER TABLE client_runtime_observations
        ADD COLUMN IF NOT EXISTS client_ip VARCHAR(45) NOT NULL DEFAULT ''
        """
    )
    op.execute(
        """
        UPDATE client_runtime_observations
        SET
            device_id = lower(btrim(device_id)),
            session_id = btrim(session_id),
            page_path = btrim(page_path),
            entry_source = btrim(entry_source),
            client_ip = btrim(COALESCE(client_ip, ''))
        """
    )
    op.execute(
        """
        DELETE FROM client_runtime_observations
        WHERE device_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
           OR session_id !~ '^[A-Za-z0-9:_\\-]{1,64}$'
           OR page_path !~ '^/[A-Za-z0-9/_\\-.]{0,254}$'
           OR entry_source !~ '^[A-Za-z0-9:_\\-]{1,64}$'
        """
    )
    op.execute(
        """
        UPDATE client_runtime_observations
        SET client_ip = ''
        WHERE client_ip <> '' AND client_ip !~ '^[0-9A-Fa-f:.]{3,45}$'
        """
    )
    op.execute(
        """
        UPDATE invite_intake_logs
        SET client_device_id = lower(btrim(COALESCE(client_device_id, '')))
        """
    )
    op.execute(
        """
        UPDATE invite_intake_logs
        SET client_device_id = ''
        WHERE client_device_id <> ''
          AND client_device_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        """
    )

    op.execute(
        """
        ALTER TABLE client_runtime_observations
        ADD CONSTRAINT ck_client_runtime_observations_client_ip_format
        CHECK (client_ip = '' OR client_ip ~ '^[0-9A-Fa-f:.]{3,45}$')
        """
    )
    op.execute(
        """
        ALTER TABLE client_runtime_observations
        ADD CONSTRAINT ck_client_runtime_observations_device_id_format
        CHECK (device_id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
        """
    )
    op.execute(
        """
        ALTER TABLE client_runtime_observations
        ADD CONSTRAINT ck_client_runtime_observations_session_id_format
        CHECK (session_id ~ '^[A-Za-z0-9:_\\-]{1,64}$')
        """
    )
    op.execute(
        """
        ALTER TABLE client_runtime_observations
        ADD CONSTRAINT ck_client_runtime_observations_page_path_format
        CHECK (page_path ~ '^/[A-Za-z0-9/_\\-.]{0,254}$')
        """
    )
    op.execute(
        """
        ALTER TABLE client_runtime_observations
        ADD CONSTRAINT ck_client_runtime_observations_entry_source_format
        CHECK (entry_source ~ '^[A-Za-z0-9:_\\-]{1,64}$')
        """
    )
    op.execute(
        """
        ALTER TABLE invite_intake_logs
        ADD CONSTRAINT ck_invite_intake_logs_client_device_id_format
        CHECK (
            client_device_id = ''
            OR client_device_id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_client_runtime_observations_client_ip_time
        ON client_runtime_observations (client_ip, occurred_at)
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
            description,
            group_name,
            config_scope,
            allowed_values
        )
        VALUES
            (
                'runtime_observation_rate_limit_requests',
                '60'::jsonb,
                '60'::jsonb,
                2,
                1,
                'Runtime observation requests per window',
                'runtime',
                'security',
                NULL
            ),
            (
                'runtime_observation_rate_limit_window_seconds',
                '60'::jsonb,
                '60'::jsonb,
                2,
                1,
                'Runtime observation window in seconds',
                'runtime',
                'security',
                NULL
            ),
            (
                'runtime_preflight_probe_rate_limit_requests',
                '20'::jsonb,
                '20'::jsonb,
                2,
                1,
                'Runtime preflight probe requests per window',
                'runtime',
                'security',
                NULL
            ),
            (
                'runtime_preflight_probe_rate_limit_window_seconds',
                '60'::jsonb,
                '60'::jsonb,
                2,
                1,
                'Runtime preflight probe window in seconds',
                'runtime',
                'security',
                NULL
            ),
            (
                'public_invite_intake_rate_limit_requests',
                '20'::jsonb,
                '20'::jsonb,
                2,
                1,
                'Public invitation intake requests per window',
                'invite',
                'security',
                NULL
            ),
            (
                'public_invite_intake_rate_limit_window_seconds',
                '60'::jsonb,
                '60'::jsonb,
                2,
                1,
                'Public invitation intake window in seconds',
                'invite',
                'security',
                NULL
            ),
            (
                'sms_verify_rate_limit_requests',
                '10'::jsonb,
                '10'::jsonb,
                2,
                1,
                'SMS verification attempts per window',
                'sms',
                'security',
                NULL
            ),
            (
                'sms_verify_rate_limit_window_seconds',
                '60'::jsonb,
                '60'::jsonb,
                2,
                1,
                'SMS verification attempt window in seconds',
                'sms',
                'security',
                NULL
            )
        ON CONFLICT (config_key) DO NOTHING
        """
    )


def downgrade() -> None:
    """Remove safety constraints/config keys introduced by this migration."""
    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'runtime_observation_rate_limit_requests',
            'runtime_observation_rate_limit_window_seconds',
            'runtime_preflight_probe_rate_limit_requests',
            'runtime_preflight_probe_rate_limit_window_seconds',
            'public_invite_intake_rate_limit_requests',
            'public_invite_intake_rate_limit_window_seconds',
            'sms_verify_rate_limit_requests',
            'sms_verify_rate_limit_window_seconds'
        )
        """
    )
    op.execute(
        """
        DROP INDEX IF EXISTS idx_client_runtime_observations_client_ip_time
        """
    )
    op.execute(
        """
        ALTER TABLE invite_intake_logs
        DROP CONSTRAINT IF EXISTS ck_invite_intake_logs_client_device_id_format
        """
    )
    op.execute(
        """
        ALTER TABLE client_runtime_observations
        DROP CONSTRAINT IF EXISTS ck_client_runtime_observations_entry_source_format
        """
    )
    op.execute(
        """
        ALTER TABLE client_runtime_observations
        DROP CONSTRAINT IF EXISTS ck_client_runtime_observations_page_path_format
        """
    )
    op.execute(
        """
        ALTER TABLE client_runtime_observations
        DROP CONSTRAINT IF EXISTS ck_client_runtime_observations_session_id_format
        """
    )
    op.execute(
        """
        ALTER TABLE client_runtime_observations
        DROP CONSTRAINT IF EXISTS ck_client_runtime_observations_device_id_format
        """
    )
    op.execute(
        """
        ALTER TABLE client_runtime_observations
        DROP CONSTRAINT IF EXISTS ck_client_runtime_observations_client_ip_format
        """
    )
    op.execute(
        """
        ALTER TABLE client_runtime_observations
        DROP COLUMN IF EXISTS client_ip
        """
    )

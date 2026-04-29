"""Finalize runtime review schema in a single migration.

Revision ID: 20260501_02
Revises: 20260427_02
Create Date: 2026-05-01 20:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260501_02"
down_revision: str | Sequence[str] | None = "20260427_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply final runtime review schema without transitional artifacts."""
    op.execute(
        """
        ALTER TABLE system_configs
        DROP CONSTRAINT IF EXISTS ck_system_configs_value_type
        """
    )
    op.execute(
        """
        ALTER TABLE system_configs
        ADD CONSTRAINT ck_system_configs_value_type
        CHECK (value_type IN (1, 2, 3, 4, 5, 6))
        """
    )

    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS review_scope INTEGER
        """
    )
    op.execute(
        """
        UPDATE users
        SET review_scope = 0
        WHERE review_scope IS NULL OR review_scope NOT IN (0, 1)
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name = 'audience_type'
            ) THEN
                UPDATE users
                SET review_scope = 1
                WHERE audience_type = 2;

                UPDATE users
                SET minor_mode_enabled = TRUE
                WHERE audience_type = 3;

                ALTER TABLE users
                DROP CONSTRAINT IF EXISTS ck_users_audience_type;
                ALTER TABLE users
                DROP COLUMN audience_type;
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN review_scope SET DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN review_scope SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE users
        DROP CONSTRAINT IF EXISTS ck_users_review_scope
        """
    )
    op.execute(
        """
        ALTER TABLE users
        ADD CONSTRAINT ck_users_review_scope
        CHECK (review_scope IN (0, 1))
        """
    )

    op.execute(
        """
        ALTER TABLE square_categories
        ADD COLUMN IF NOT EXISTS minor_visible BOOLEAN
        """
    )
    op.execute(
        """
        ALTER TABLE square_categories
        ADD COLUMN IF NOT EXISTS review_visibility_scope INTEGER
        """
    )
    op.execute(
        """
        UPDATE square_categories
        SET minor_visible = FALSE
        WHERE minor_visible IS NULL
        """
    )
    op.execute(
        """
        UPDATE square_categories
        SET review_visibility_scope = 1
        WHERE review_visibility_scope IS NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'square_categories'
                  AND column_name = 'visibility_scope'
            ) THEN
                UPDATE square_categories
                SET review_visibility_scope = CASE
                    WHEN visibility_scope = 2 THEN 2
                    WHEN visibility_scope IN (1, 3) THEN 1
                    ELSE COALESCE(review_visibility_scope, 1)
                END;
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        """
        UPDATE square_categories
        SET review_visibility_scope = 1
        WHERE review_visibility_scope NOT IN (0, 1, 2, 3)
        """
    )
    op.execute(
        """
        ALTER TABLE square_categories
        ALTER COLUMN minor_visible SET DEFAULT FALSE
        """
    )
    op.execute(
        """
        ALTER TABLE square_categories
        ALTER COLUMN review_visibility_scope SET DEFAULT 1
        """
    )
    op.execute(
        """
        ALTER TABLE square_categories
        ALTER COLUMN minor_visible SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE square_categories
        ALTER COLUMN review_visibility_scope SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE square_categories
        DROP CONSTRAINT IF EXISTS ck_square_categories_visibility_scope
        """
    )
    op.execute(
        """
        ALTER TABLE square_categories
        DROP COLUMN IF EXISTS visibility_scope
        """
    )
    op.execute(
        """
        ALTER TABLE square_categories
        DROP CONSTRAINT IF EXISTS ck_square_categories_review_visibility_scope
        """
    )
    op.execute(
        """
        ALTER TABLE square_categories
        ADD CONSTRAINT ck_square_categories_review_visibility_scope
        CHECK (review_visibility_scope IN (0, 1, 2, 3))
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS client_runtime_observations (
            id BIGINT PRIMARY KEY,
            client_type VARCHAR(32) NOT NULL,
            device_id VARCHAR(64) NOT NULL DEFAULT '',
            session_id VARCHAR(64) NOT NULL DEFAULT '',
            user_id BIGINT NULL REFERENCES users(id) ON DELETE SET NULL,
            user_agent VARCHAR(2048) NOT NULL DEFAULT '',
            platform VARCHAR(32) NOT NULL DEFAULT '',
            os_version VARCHAR(64) NOT NULL DEFAULT '',
            app_version VARCHAR(32) NOT NULL DEFAULT '',
            build_id VARCHAR(64) NOT NULL DEFAULT '',
            build_time TIMESTAMPTZ NULL,
            network_type VARCHAR(32) NOT NULL DEFAULT '',
            scope_snapshot INTEGER NOT NULL DEFAULT 0,
            feature_hits JSONB NOT NULL DEFAULT '[]'::jsonb,
            ua_fetch_status INTEGER NOT NULL DEFAULT 0,
            event_name VARCHAR(64) NOT NULL,
            page_path VARCHAR(255) NOT NULL DEFAULT '',
            entry_source VARCHAR(64) NOT NULL DEFAULT '',
            event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            event_payload_digest VARCHAR(64) NOT NULL DEFAULT '',
            request_id VARCHAR(128) NOT NULL DEFAULT '',
            occurred_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_client_runtime_observations_scope_snapshot
                CHECK (scope_snapshot IN (0, 1)),
            CONSTRAINT ck_client_runtime_observations_ua_fetch_status
                CHECK (ua_fetch_status IN (0, 1, 2, 3))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_client_runtime_observations_client_time
        ON client_runtime_observations (client_type, occurred_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_client_runtime_observations_device_event_time
        ON client_runtime_observations (device_id, event_name, occurred_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_client_runtime_observations_scope_time
        ON client_runtime_observations (scope_snapshot, occurred_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_client_runtime_observations_session_time
        ON client_runtime_observations (session_id, occurred_at)
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'invite_recognition_logs'
            ) THEN
                ALTER TABLE invite_recognition_logs
                ADD COLUMN IF NOT EXISTS reviewer_flag_snapshot INTEGER NOT NULL DEFAULT 0;
                ALTER TABLE invite_recognition_logs
                ADD COLUMN IF NOT EXISTS runtime_observation_id BIGINT NULL;
                ALTER TABLE invite_recognition_logs
                ADD COLUMN IF NOT EXISTS client_user_agent VARCHAR(2048) NOT NULL DEFAULT '';
                ALTER TABLE invite_recognition_logs
                ADD COLUMN IF NOT EXISTS client_device_id VARCHAR(64) NOT NULL DEFAULT '';

                CREATE SEQUENCE IF NOT EXISTS invite_intake_logs_id_seq;
                CREATE TABLE IF NOT EXISTS invite_intake_logs (
                    id INTEGER PRIMARY KEY DEFAULT nextval('invite_intake_logs_id_seq'::regclass),
                    actor_user_id BIGINT NULL REFERENCES users(id) ON DELETE SET NULL,
                    source VARCHAR(32) NOT NULL,
                    trigger VARCHAR(32) NOT NULL DEFAULT 'unknown',
                    raw_text TEXT NOT NULL,
                    first_candidate VARCHAR(6) NULL,
                    recognized_code VARCHAR(6) NULL,
                    invite_code_id INTEGER NULL REFERENCES invite_codes(id) ON DELETE SET NULL,
                    valid BOOLEAN NOT NULL DEFAULT FALSE,
                    bindable BOOLEAN NULL,
                    reviewer_flag_snapshot INTEGER NOT NULL DEFAULT 0,
                    runtime_observation_id BIGINT NULL
                        REFERENCES client_runtime_observations(id) ON DELETE SET NULL,
                    client_user_agent VARCHAR(2048) NOT NULL DEFAULT '',
                    client_device_id VARCHAR(64) NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT ck_invite_intake_logs_source
                        CHECK (
                            source IN (
                                'login',
                                'setup',
                                'link',
                                'invite_bind_page',
                                'invite_share_page'
                            )
                        ),
                    CONSTRAINT ck_invite_intake_logs_trigger_format
                        CHECK (trigger ~ '^[a-z0-9_\\-]{1,32}$'),
                    CONSTRAINT ck_invite_intake_logs_first_candidate_format
                        CHECK (first_candidate IS NULL OR first_candidate ~ '^[A-Z0-9]{6}$'),
                    CONSTRAINT ck_invite_intake_logs_recognized_code_format
                        CHECK (recognized_code IS NULL OR recognized_code ~ '^[A-Z0-9]{6}$'),
                    CONSTRAINT ck_invite_intake_logs_reviewer_flag_snapshot
                        CHECK (reviewer_flag_snapshot IN (0, 1))
                );

                INSERT INTO invite_intake_logs (
                    id,
                    actor_user_id,
                    source,
                    trigger,
                    raw_text,
                    first_candidate,
                    recognized_code,
                    invite_code_id,
                    valid,
                    bindable,
                    reviewer_flag_snapshot,
                    runtime_observation_id,
                    client_user_agent,
                    client_device_id,
                    created_at
                )
                SELECT
                    id,
                    actor_user_id,
                    source,
                    trigger,
                    raw_text,
                    first_candidate,
                    recognized_code,
                    invite_code_id,
                    valid,
                    bindable,
                    COALESCE(reviewer_flag_snapshot, 0),
                    runtime_observation_id,
                    COALESCE(client_user_agent, ''),
                    COALESCE(client_device_id, ''),
                    created_at
                FROM invite_recognition_logs;

                PERFORM setval(
                    'invite_intake_logs_id_seq',
                    GREATEST(COALESCE((SELECT MAX(id) FROM invite_intake_logs), 0), 1),
                    (SELECT COUNT(1) > 0 FROM invite_intake_logs)
                );

                DROP TABLE invite_recognition_logs;
                DROP SEQUENCE IF EXISTS invite_recognition_logs_id_seq;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_invite_intake_logs_created_at
        ON invite_intake_logs (created_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_invite_intake_logs_source_created_at
        ON invite_intake_logs (source, created_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_invite_intake_logs_recognized_code
        ON invite_intake_logs (recognized_code)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_invite_intake_logs_runtime_observation
        ON invite_intake_logs (runtime_observation_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_invite_intake_logs_device_created_at
        ON invite_intake_logs (client_device_id, created_at)
        """
    )

    op.execute("DROP TABLE IF EXISTS client_connectivity_events")


def downgrade() -> None:
    """Downgrade is intentionally unsupported."""
    raise RuntimeError("Downgrade is not supported for migration 20260501_02")

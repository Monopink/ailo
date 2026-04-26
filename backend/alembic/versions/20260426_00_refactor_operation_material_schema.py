"""Consolidate invitation share configuration and finalize system_configs shape model.

Revision ID: 20260426_00
Revises: 20260425_00
Create Date: 2026-04-26 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260426_00"
down_revision: str | Sequence[str] | None = "20260425_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _check_constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(
        constraint["name"] == constraint_name
        for constraint in inspector.get_check_constraints(table_name)
    )


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _add_system_config_scope() -> None:
    column_names = _get_column_names("system_configs")
    if "config_scope" not in column_names:
        op.add_column(
            "system_configs",
            sa.Column(
                "config_scope",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'system'"),
                comment="Configuration scope: system/security/operation",
            ),
        )

    if not _check_constraint_exists("system_configs", "ck_system_configs_scope"):
        with op.batch_alter_table("system_configs") as batch_op:
            batch_op.create_check_constraint(
                "ck_system_configs_scope",
                "config_scope IN ('system', 'security', 'operation')",
            )

    if not _index_exists("system_configs", "idx_system_configs_scope"):
        op.create_index(
            "idx_system_configs_scope", "system_configs", ["config_scope"], unique=False
        )


def _validate_scalar_config_text_values() -> None:
    """Fail migration immediately when runtime config_value text is dirty."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM system_configs
                WHERE config_type = 2
                  AND (btrim(config_value) = '' OR btrim(config_value) !~ '^-?[0-9]+$')
            ) THEN
                RAISE EXCEPTION 'Invalid NUMBER config_value in system_configs';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM system_configs
                WHERE config_type = 3
                  AND lower(btrim(config_value)) NOT IN (
                      'true',
                      'false',
                      '1',
                      '0',
                      'yes',
                      'no',
                      'on',
                      'off'
                  )
            ) THEN
                RAISE EXCEPTION 'Invalid BOOLEAN config_value in system_configs';
            END IF;
        END;
        $$;
        """
    )


def _convert_system_config_value_columns_to_jsonb() -> None:
    """Convert config_value/default_value from TEXT to JSONB."""
    _validate_scalar_config_text_values()

    op.alter_column(
        "system_configs",
        "config_value",
        existing_type=sa.Text(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using="""
            CASE
                WHEN config_type = 2 THEN to_jsonb((btrim(config_value))::bigint)
                WHEN config_type = 3 THEN
                    CASE
                        WHEN lower(btrim(config_value)) IN ('true', '1', 'yes', 'on')
                            THEN 'true'::jsonb
                        WHEN lower(btrim(config_value)) IN ('false', '0', 'no', 'off')
                            THEN 'false'::jsonb
                        ELSE NULL
                    END
                WHEN config_type = 4 THEN config_value::jsonb
                ELSE to_jsonb(config_value)
            END
        """,
    )

    op.alter_column(
        "system_configs",
        "default_value",
        existing_type=sa.Text(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using="""
            CASE
                WHEN config_type = 2 THEN
                    CASE
                        WHEN btrim(default_value) = '' THEN to_jsonb(''::text)
                        ELSE to_jsonb((btrim(default_value))::bigint)
                    END
                WHEN config_type = 3 THEN
                    CASE
                        WHEN btrim(default_value) = '' THEN to_jsonb(''::text)
                        WHEN lower(btrim(default_value)) IN ('true', '1', 'yes', 'on')
                            THEN 'true'::jsonb
                        WHEN lower(btrim(default_value)) IN ('false', '0', 'no', 'off')
                            THEN 'false'::jsonb
                        ELSE to_jsonb(''::text)
                    END
                WHEN config_type = 4 THEN
                    CASE
                        WHEN btrim(default_value) = '' THEN to_jsonb(''::text)
                        ELSE default_value::jsonb
                    END
                ELSE to_jsonb(default_value)
            END
        """,
    )


def _migrate_invite_share_configs() -> None:
    op.execute(
        """
        WITH dedup_templates AS (
            SELECT DISTINCT ON (btrim(ist.template_text))
                btrim(ist.template_text) AS template_text,
                ist.priority,
                ist.id
            FROM invite_share_templates ist
            WHERE ist.status = 1
              AND btrim(ist.template_text) <> ''
            ORDER BY btrim(ist.template_text), ist.priority ASC, ist.id DESC
        ),
        payload AS (
            SELECT
                COALESCE(
                    jsonb_agg(to_jsonb(template_text) ORDER BY priority ASC, id DESC),
                    '["来敲敲AI {{code}} {{link}}"]'::jsonb
                ) AS config_value,
                COALESCE(
                    (jsonb_agg(to_jsonb(template_text) ORDER BY priority ASC, id DESC) #>> '{0}'),
                    '来敲敲AI {{code}} {{link}}'
                ) AS default_text
            FROM dedup_templates
        )
        INSERT INTO system_configs (
            config_key,
            config_value,
            default_value,
            config_type,
            description,
            group_name,
            allowed_values,
            config_scope
        )
        VALUES (
            'invite_share_command_texts',
            (SELECT config_value FROM payload),
            to_jsonb((SELECT default_text FROM payload)),
            1,
            'Invite share command text templates',
            'operation',
            NULL,
            'operation'
        )
        ON CONFLICT (config_key) DO UPDATE
        SET
            config_value = EXCLUDED.config_value,
            default_value = EXCLUDED.default_value,
            config_type = EXCLUDED.config_type,
            description = EXCLUDED.description,
            group_name = EXCLUDED.group_name,
            allowed_values = EXCLUDED.allowed_values,
            config_scope = EXCLUDED.config_scope,
            updated_at = NOW()
        """,
    )

    op.execute(
        """
        WITH dedup_titles AS (
            SELECT DISTINCT ON (btrim(osc.title))
                btrim(osc.title) AS title,
                osc.priority,
                osc.id
            FROM operation_slot_configs osc
            WHERE osc.status = 1
              AND osc.slot_code = 'invite_share_card'
              AND osc.channel = 'mini_program'
              AND btrim(osc.title) <> ''
            ORDER BY btrim(osc.title), osc.priority ASC, osc.id DESC
        ),
        payload AS (
            SELECT
                COALESCE(
                    jsonb_agg(to_jsonb(title) ORDER BY priority ASC, id DESC),
                    '["来敲敲AI，对话敲多新奇有趣"]'::jsonb
                ) AS config_value,
                COALESCE(
                    (jsonb_agg(to_jsonb(title) ORDER BY priority ASC, id DESC) #>> '{0}'),
                    '来敲敲AI，对话敲多新奇有趣'
                ) AS default_text
            FROM dedup_titles
        )
        INSERT INTO system_configs (
            config_key,
            config_value,
            default_value,
            config_type,
            description,
            group_name,
            allowed_values,
            config_scope
        )
        VALUES (
            'invite_share_card_titles',
            (SELECT config_value FROM payload),
            to_jsonb((SELECT default_text FROM payload)),
            1,
            'Invite share card title templates',
            'operation',
            NULL,
            'operation'
        )
        ON CONFLICT (config_key) DO UPDATE
        SET
            config_value = EXCLUDED.config_value,
            default_value = EXCLUDED.default_value,
            config_type = EXCLUDED.config_type,
            description = EXCLUDED.description,
            group_name = EXCLUDED.group_name,
            allowed_values = EXCLUDED.allowed_values,
            config_scope = EXCLUDED.config_scope,
            updated_at = NOW()
        """,
    )


def _assert_invite_share_json_arrays() -> None:
    """Fail migration when invite share config payload shape is invalid."""
    op.execute(
        """
        DO $$
        DECLARE
            invalid_key text;
        BEGIN
            SELECT sc.config_key
            INTO invalid_key
            FROM system_configs sc
            WHERE sc.config_key IN (
                'invite_share_command_texts',
                'invite_share_card_titles'
            )
              AND (
                    jsonb_typeof(sc.config_value) <> 'array'
                    OR jsonb_array_length(sc.config_value) = 0
                    OR EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(sc.config_value) AS elem
                        WHERE jsonb_typeof(elem) <> 'string'
                           OR btrim(elem #>> '{}') = ''
                    )
              )
            LIMIT 1;

            IF invalid_key IS NOT NULL THEN
                RAISE EXCEPTION 'Invalid JSON array payload for %', invalid_key;
            END IF;
        END;
        $$;
        """
    )


def _classify_system_configs() -> None:
    op.execute(
        """
        UPDATE system_configs
        SET config_scope = 'security'
        WHERE config_key IN (
            'leancloud_im_webhook_token',
            'admin_auth_whitelist',
            'sms_whitelist'
        )
        """
    )

    op.execute(
        """
        UPDATE system_configs
        SET config_scope = 'operation'
        WHERE config_key IN (
            'invite_share_command_texts',
            'invite_share_card_titles',
            'default_nickname_prefix',
            'default_nickname_suffix_length'
        )
           OR group_name = 'contacts'
        """
    )


def _normalize_avatar_allowed_formats_config() -> None:
    """Normalize avatar_allowed_formats into ARRAY(string) shape with scalar default."""
    op.execute(
        """
        UPDATE system_configs
        SET config_value = COALESCE(
            (
                SELECT CASE
                    WHEN COUNT(*) = 0 THEN NULL
                    ELSE jsonb_agg(to_jsonb(item) ORDER BY ord)
                END
                FROM (
                    SELECT
                        btrim(elem.value #>> '{}') AS item,
                        elem.ord
                    FROM jsonb_array_elements(
                        CASE
                            WHEN jsonb_typeof(system_configs.config_value) = 'array'
                                THEN system_configs.config_value
                            WHEN jsonb_typeof(system_configs.config_value) = 'string'
                                THEN to_jsonb(
                                    string_to_array(system_configs.config_value #>> '{}', ',')
                                )
                            ELSE '[]'::jsonb
                        END
                    ) WITH ORDINALITY AS elem(value, ord)
                    WHERE btrim(elem.value #>> '{}') <> ''
                ) AS normalized_items
            ),
            '["image/jpeg","image/png","image/webp"]'::jsonb
        )
        WHERE config_key = 'avatar_allowed_formats'
        """
    )

    op.execute(
        """
        UPDATE system_configs
        SET default_value = to_jsonb('image/webp'::text)
        WHERE config_key = 'avatar_allowed_formats'
        """
    )


def _cleanup_deprecated_invite_share_keys() -> None:
    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'operation_invite_share_command_text',
            'operation_invite_share_card_title',
            'operation_invite_share_card_image_url',
            'operation_invite_share_text'
        )
        """
    )


def _cleanup_deprecated_growth_cap_keys() -> None:
    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'default_contact_limit',
            'growth_new_user_reward_window_days',
            'growth_new_user_reward_cap_total'
        )
        """
    )


def _drop_deprecated_invite_operation_tables() -> None:
    op.drop_table("operation_slot_configs")
    op.drop_table("operation_publish_logs")
    op.drop_table("operation_assets")
    op.drop_table("invite_share_templates")


def _rename_config_type_to_value_type() -> None:
    column_names = _get_column_names("system_configs")
    if "config_type" in column_names and "value_type" not in column_names:
        op.alter_column(
            "system_configs",
            "config_type",
            new_column_name="value_type",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )


def _ensure_value_type_constraint() -> None:
    if _check_constraint_exists("system_configs", "ck_system_configs_type"):
        with op.batch_alter_table("system_configs") as batch_op:
            batch_op.drop_constraint("ck_system_configs_type", type_="check")

    if not _check_constraint_exists("system_configs", "ck_system_configs_value_type"):
        with op.batch_alter_table("system_configs") as batch_op:
            batch_op.create_check_constraint(
                "ck_system_configs_value_type",
                "value_type IN (1, 2, 3, 4, 5)",
            )


def _ensure_config_shape_column() -> None:
    column_names = _get_column_names("system_configs")
    if "config_shape" not in column_names:
        op.add_column(
            "system_configs",
            sa.Column(
                "config_shape",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
                comment="Config shape: 1=single value, 2=array value",
            ),
        )

    op.execute(
        """
        UPDATE system_configs
        SET config_shape = CASE
            WHEN jsonb_typeof(config_value) = 'array' THEN 2
            ELSE 1
        END
        """
    )

    if not _check_constraint_exists("system_configs", "ck_system_configs_shape"):
        with op.batch_alter_table("system_configs") as batch_op:
            batch_op.create_check_constraint(
                "ck_system_configs_shape",
                "config_shape IN (1, 2)",
            )

    op.alter_column(
        "system_configs",
        "config_shape",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=None,
    )


def _normalize_array_default_values() -> None:
    op.execute(
        """
        UPDATE system_configs
        SET default_value = CASE
            WHEN jsonb_typeof(default_value) = 'array'
                THEN COALESCE(default_value -> 0, to_jsonb(''::text))
            WHEN jsonb_typeof(default_value) IN ('string', 'number', 'boolean', 'null')
                THEN default_value
            ELSE to_jsonb(''::text)
        END
        WHERE config_shape = 2
        """
    )


def _assert_value_shape_consistency() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM system_configs
                WHERE config_shape = 2
                  AND jsonb_typeof(config_value) <> 'array'
            ) THEN
                RAISE EXCEPTION 'config_shape=ARRAY requires config_value JSON array';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM system_configs
                WHERE config_shape = 2
                  AND jsonb_typeof(config_value) = 'array'
                  AND jsonb_array_length(config_value) = 0
            ) THEN
                RAISE EXCEPTION 'config_shape=ARRAY requires non-empty config_value array';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM system_configs
                WHERE config_shape = 2
                  AND jsonb_typeof(default_value) NOT IN ('string', 'number', 'boolean', 'null')
            ) THEN
                RAISE EXCEPTION 'config_shape=ARRAY requires scalar default_value';
            END IF;
        END;
        $$;
        """
    )


def upgrade() -> None:
    """Apply invitation share and system config refactor."""
    _add_system_config_scope()
    _convert_system_config_value_columns_to_jsonb()
    _migrate_invite_share_configs()
    _assert_invite_share_json_arrays()
    _classify_system_configs()
    _normalize_avatar_allowed_formats_config()
    _cleanup_deprecated_invite_share_keys()
    _cleanup_deprecated_growth_cap_keys()
    _drop_deprecated_invite_operation_tables()
    _rename_config_type_to_value_type()
    _ensure_value_type_constraint()
    _ensure_config_shape_column()
    _normalize_array_default_values()
    _assert_value_shape_consistency()


def downgrade() -> None:
    """Downgrade is intentionally unsupported."""
    raise RuntimeError("Downgrade is not supported for migration 20260426_00")

"""Align global unique placeholder check to system config source.

Revision ID: 20260524_01
Revises: 20260522_03
Create Date: 2026-05-24 16:45:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260524_01"
down_revision: str | Sequence[str] | None = "20260522_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONFIG_KEY = "ai_global_unique_placeholder_keys"
_CONFIG_SCOPE = "operation"
_CONFIG_GROUP_NAME = "ai"
_CONFIG_VALUE_JSON = '["name"]'
_DEFAULT_VALUE_JSON = '"name"'


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    constraints = inspector.get_unique_constraints(table_name)
    return any(constraint.get("name") == constraint_name for constraint in constraints)


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    columns = inspector.get_columns(table_name)
    return any(column.get("name") == column_name for column in columns)


def upgrade() -> None:
    """Apply schema and seed changes for global unique placeholder config source."""
    if _column_exists("ai_personality_placeholders", "is_global_unique"):
        op.drop_column("ai_personality_placeholders", "is_global_unique")

    if not _constraint_exists(
        "ai_personality_placeholders", "uq_ai_personality_placeholders_personality_key"
    ):
        op.create_unique_constraint(
            "uq_ai_personality_placeholders_personality_key",
            "ai_personality_placeholders",
            ["personality_id", "placeholder_key"],
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_templates_prompt_variables_gin "
        "ON ai_templates USING gin (prompt_variables)"
    )

    op.execute(
        sa.text(
            "INSERT INTO system_configs "
            "(config_key, config_value, default_value, value_type, config_shape, config_scope, "
            "description, group_name, allowed_values) "
            "VALUES ("
            ":config_key, "
            "CAST(:config_value AS jsonb), "
            "CAST(:default_value AS jsonb), "
            "1, "
            "2, "
            ":config_scope, "
            "'Global unique placeholder keys for template advanced edit conflict check', "
            ":group_name, "
            "NULL"
            ") "
            "ON CONFLICT (config_key) DO UPDATE SET "
            "config_value = EXCLUDED.config_value, "
            "default_value = EXCLUDED.default_value, "
            "value_type = EXCLUDED.value_type, "
            "config_shape = EXCLUDED.config_shape, "
            "config_scope = EXCLUDED.config_scope, "
            "description = EXCLUDED.description, "
            "group_name = EXCLUDED.group_name, "
            "allowed_values = EXCLUDED.allowed_values"
        ).bindparams(
            config_key=_CONFIG_KEY,
            config_value=_CONFIG_VALUE_JSON,
            default_value=_DEFAULT_VALUE_JSON,
            config_scope=_CONFIG_SCOPE,
            group_name=_CONFIG_GROUP_NAME,
        )
    )


def downgrade() -> None:
    """Revert schema and seed changes for global unique placeholder config source."""
    op.execute(
        sa.text("DELETE FROM system_configs WHERE config_key = :config_key").bindparams(
            config_key=_CONFIG_KEY
        )
    )
    op.execute("DROP INDEX IF EXISTS idx_ai_templates_prompt_variables_gin")
    if _constraint_exists(
        "ai_personality_placeholders", "uq_ai_personality_placeholders_personality_key"
    ):
        op.drop_constraint(
            "uq_ai_personality_placeholders_personality_key",
            "ai_personality_placeholders",
            type_="unique",
        )
    if not _column_exists("ai_personality_placeholders", "is_global_unique"):
        op.add_column(
            "ai_personality_placeholders",
            sa.Column(
                "is_global_unique",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.alter_column(
            "ai_personality_placeholders",
            "is_global_unique",
            server_default=None,
        )

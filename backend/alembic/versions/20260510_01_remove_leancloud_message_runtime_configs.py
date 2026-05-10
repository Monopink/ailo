"""Remove legacy LeanCloud configs and apply websocket delivery schema fields.

Revision ID: 20260510_01
Revises: 20260507_03
Create Date: 2026-05-10 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260510_01"
down_revision: str | Sequence[str] | None = "20260507_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Delete LeanCloud runtime configs and add websocket delivery tracking fields."""
    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'leancloud_im_server_url',
            'leancloud_im_service_conversation_id',
            'leancloud_im_webhook_token'
        )
        """
    )
    op.add_column(
        "message_endpoints",
        sa.Column("owner_instance_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "message_endpoints",
        sa.Column("owner_lease_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_message_endpoints_owner_instance_id",
        "message_endpoints",
        ["owner_instance_id"],
        unique=False,
    )
    op.create_index(
        "idx_message_endpoints_owner_lease_expires_at",
        "message_endpoints",
        ["owner_lease_expires_at"],
        unique=False,
    )
    op.add_column(
        "notification_push_history",
        sa.Column("msg_id_server", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "notification_push_history",
        sa.Column("planned_endpoint_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "notification_push_history",
        sa.Column("completed_endpoint_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "notification_push_history",
        sa.Column("succeeded_endpoint_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "idx_notification_push_msg_id_server",
        "notification_push_history",
        ["msg_id_server"],
        unique=False,
    )
    op.execute(
        """
        UPDATE notification_push_history
        SET status = 1
        WHERE status NOT IN (1, 2)
        """
    )
    op.alter_column(
        "notification_push_history",
        "planned_endpoint_count",
        server_default=None,
        existing_type=sa.Integer(),
    )
    op.alter_column(
        "notification_push_history",
        "completed_endpoint_count",
        server_default=None,
        existing_type=sa.Integer(),
    )
    op.alter_column(
        "notification_push_history",
        "succeeded_endpoint_count",
        server_default=None,
        existing_type=sa.Integer(),
    )


def downgrade() -> None:
    """Rollback websocket delivery fields and restore LeanCloud runtime configs."""
    op.drop_index("idx_notification_push_msg_id_server", table_name="notification_push_history")
    op.drop_column("notification_push_history", "succeeded_endpoint_count")
    op.drop_column("notification_push_history", "completed_endpoint_count")
    op.drop_column("notification_push_history", "planned_endpoint_count")
    op.drop_column("notification_push_history", "msg_id_server")
    op.drop_index("idx_message_endpoints_owner_lease_expires_at", table_name="message_endpoints")
    op.drop_index("idx_message_endpoints_owner_instance_id", table_name="message_endpoints")
    op.drop_column("message_endpoints", "owner_lease_expires_at")
    op.drop_column("message_endpoints", "owner_instance_id")
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
            allowed_values,
            config_scope
        )
        VALUES
            (
                'leancloud_im_server_url',
                to_jsonb(''::text),
                to_jsonb(''::text),
                1,
                1,
                'LeanCloud IM server URL',
                'im_leancloud',
                NULL,
                'system'
            ),
            (
                'leancloud_im_service_conversation_id',
                to_jsonb(''::text),
                to_jsonb(''::text),
                1,
                1,
                'LeanCloud IM system conversation ID for message routing',
                'im_leancloud',
                NULL,
                'system'
            ),
            (
                'leancloud_im_webhook_token',
                to_jsonb(''::text),
                to_jsonb(''::text),
                1,
                1,
                'LeanCloud IM webhook security token (24-character URL-safe string)',
                'im_leancloud',
                NULL,
                'security'
            )
        ON CONFLICT (config_key) DO NOTHING
        """
    )

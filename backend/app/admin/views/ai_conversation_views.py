"""
AI Conversation admin views.

This module contains Starlette-Admin views for AI conversation management
(message buffer, conversation items, and archives).
"""

from typing import Any

from admin.fields import LocalDateTimeField
from admin.views.base import IntegerEnumField
from enums import AIMessageBufferState
from models.ai.instance import (
    AIConversationItem,
    AIConversationItemArchive,
    AIConversationState,
    AIMessageBuffer,
)
from starlette.requests import Request
from starlette_admin import IntegerField, JSONField, StringField, TextAreaField
from starlette_admin.contrib.sqla import ModelView


class AIMessageBufferView(ModelView):
    """AI Message Buffer view - message aggregation window management."""

    exclude_fields_from_create = [
        "id",
        "aggregate_state",
        "micro_expires_at_ms",
        "macro_expires_at_ms",
        "buffer_expires_at_ms",
        "last_message_category",
        "first_msg_id_client",
        "last_msg_id_client",
        "message_count",
        "last_msg_time_ms",
        "locked_at",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_list = [
        "micro_expires_at_ms",
        "macro_expires_at_ms",
        "buffer_expires_at_ms",
        "last_message_category",
        "first_msg_id_client",
        "last_msg_id_client",
        "last_msg_time_ms",
    ]

    async def edit(self, request: Request, pk: Any, data: dict[str, Any]) -> Any:
        """Normalize optional integer fields before persisting."""
        # Convert string to int or None for optional BIGINT fields
        bigint_fields = [
            "micro_expires_at_ms",
            "macro_expires_at_ms",
            "buffer_expires_at_ms",
            "last_msg_time_ms",
            "wake_expires_at_ms",
        ]
        for field in bigint_fields:
            if field in data:
                value = data[field]
                if value == "" or value is None:
                    data[field] = None
                elif isinstance(value, str):
                    try:
                        data[field] = int(value)
                    except ValueError:
                        data[field] = None

        # Convert empty string to None for optional string fields
        if data.get("last_message_category") == "":
            data["last_message_category"] = None

        return await super().edit(request, pk, data)

    def can_create(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["id", "user_qiao_id", "instance_qiao_id"]
    sortable_fields = [
        "id",
        "user_qiao_id",
        "instance_qiao_id",
        "aggregate_state",
        "message_count",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="Buffer ID", help_text="Internal buffer ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external ID"),
        StringField("instance_qiao_id", label="Instance Qiao ID", help_text="Instance external ID"),
        IntegerEnumField(
            "aggregate_state",
            enum=AIMessageBufferState,
            label="State",
            help_text="Buffer state: OPEN/LOCKED/COMPLETE/CANCELLED",
        ),
        StringField(
            "micro_expires_at_ms",
            label="Micro Timer (ms)",
            help_text="Micro timer expiration timestamp",
        ),
        StringField(
            "macro_expires_at_ms",
            label="Macro Timer (ms)",
            help_text="Macro timer expiration timestamp",
        ),
        StringField(
            "buffer_expires_at_ms",
            label="Next Deadline (ms)",
            help_text="Next timer deadline (min of micro/macro)",
        ),
        StringField(
            "last_message_category",
            label="Last Message Category",
            help_text="Last inbound message category",
        ),
        StringField(
            "first_msg_id_client",
            label="First Client Msg ID",
            help_text="First client message ID within buffer",
        ),
        StringField(
            "last_msg_id_client",
            label="Last Client Msg ID",
            help_text="Last client message ID within buffer",
        ),
        IntegerField(
            "message_count", label="Message Count", help_text="Number of messages in buffer"
        ),
        StringField(
            "last_msg_time_ms",
            label="Last Message Time (ms)",
            help_text="Timestamp of last message appended to buffer",
        ),
        LocalDateTimeField(
            "locked_at", label="Locked At", help_text="Timestamp when buffer entered LOCKED state"
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Buffer creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


class AIConversationItemView(ModelView):
    """AI Conversation Item view - conversation history stored in simple fields."""

    exclude_fields_from_create = [
        "id",
        "created_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "user_qiao_id",
        "instance_qiao_id",
        "role",
        "buffer_id",
        "created_at",
    ]
    exclude_fields_from_list = []

    async def edit(self, request: Request, pk: Any, data: dict[str, Any]) -> Any:
        """Normalize optional fields before persisting."""
        if not data.get("client_msg_ids"):
            data["client_msg_ids"] = []
        if not data.get("media_url"):
            data["media_url"] = None
        return await super().edit(request, pk, data)

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = [
        "id",
        "user_qiao_id",
        "instance_qiao_id",
        "role",
        "text_content",
    ]
    sortable_fields = [
        "id",
        "user_qiao_id",
        "instance_qiao_id",
        "role",
        "buffer_id",
        "is_excluded_from_context",
        "created_at",
    ]

    fields = [
        StringField("id", label="Item ID", help_text="Internal conversation item ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external ID"),
        StringField("instance_qiao_id", label="Instance Qiao ID", help_text="Instance external ID"),
        StringField("role", label="Role", help_text="Message role: system/user/assistant"),
        StringField("message_type", label="Message Type", help_text="text/image/audio"),
        TextAreaField(
            "text_content",
            label="Text Content",
            help_text="Stored text message content (for text messages)",
        ),
        StringField("media_url", label="Media URL", help_text="Media URL for image/audio messages"),
        JSONField(
            "media_metadata",
            label="Media Metadata",
            help_text="JSON metadata (dimensions, transcript, duration, etc.)",
        ),
        JSONField(
            "client_msg_ids",
            label="Client Message IDs",
            help_text="Client message IDs merged into this row",
        ),
        StringField(
            "buffer_id", label="Buffer ID", help_text="Associated buffer ID (user role only)"
        ),
        IntegerEnumField(
            "is_excluded_from_context",
            choices=[(0, "Included"), (1, "Excluded")],
            label="Context Status",
            help_text="Whether this item is included in LLM context",
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Item creation time"),
    ]


class AIConversationItemArchiveView(ModelView):
    """AI Conversation Item Archive view - archived conversation history."""

    exclude_fields_from_create = [
        "id",
        "user_qiao_id",
        "instance_qiao_id",
        "role",
        "message_type",
        "text_content",
        "media_url",
        "media_metadata",
        "client_msg_ids",
        "buffer_id",
        "is_excluded_from_context",
        "created_at",
        "archived_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "user_qiao_id",
        "instance_qiao_id",
        "role",
        "message_type",
        "text_content",
        "media_url",
        "media_metadata",
        "client_msg_ids",
        "buffer_id",
        "is_excluded_from_context",
        "created_at",
        "archived_at",
    ]

    async def edit(self, request: Request, pk: Any, data: dict[str, Any]) -> Any:
        """Normalize optional fields before persisting."""
        if not data.get("client_msg_ids"):
            data["client_msg_ids"] = []
        return await super().edit(request, pk, data)

    exclude_fields_from_list = []

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("archived_at", True)]
    searchable_fields = [
        "id",
        "user_qiao_id",
        "instance_qiao_id",
        "role",
        "text_content",
    ]
    sortable_fields = [
        "id",
        "user_qiao_id",
        "instance_qiao_id",
        "role",
        "buffer_id",
        "is_excluded_from_context",
        "created_at",
        "archived_at",
    ]

    fields = [
        StringField("id", label="Item ID", help_text="Internal conversation item ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external ID"),
        StringField("instance_qiao_id", label="Instance Qiao ID", help_text="Instance external ID"),
        StringField("role", label="Role", help_text="Message role: system/user/assistant"),
        StringField("message_type", label="Message Type", help_text="text/image/audio"),
        TextAreaField(
            "text_content",
            label="Text Content",
            help_text="Stored text content (if applicable)",
        ),
        StringField("media_url", label="Media URL", help_text="Media URL for image/audio messages"),
        JSONField(
            "media_metadata",
            label="Media Metadata",
            help_text="JSON metadata (dimensions, transcript, duration, etc.)",
        ),
        JSONField(
            "client_msg_ids",
            label="Client Message IDs",
            help_text="Client message IDs merged into this row",
        ),
        StringField(
            "buffer_id", label="Buffer ID", help_text="Associated buffer ID (user role only)"
        ),
        IntegerEnumField(
            "is_excluded_from_context",
            choices=[(0, "Included"), (1, "Excluded")],
            label="Context Status",
            help_text="Whether this item is included in LLM context",
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Original creation time"),
        LocalDateTimeField("archived_at", label="Archived At", help_text="Archive timestamp"),
    ]


class AIConversationStateView(ModelView):
    """AI Conversation State view - manages pending messages and interruption state."""

    exclude_fields_from_create = [
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit = [
        "user_qiao_id",
        "instance_qiao_id",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_list = []

    async def edit(self, request: Request, pk: Any, data: dict[str, Any]) -> Any:
        """Normalize optional fields before persisting."""
        # Ensure pending_messages is None if empty
        if not data.get("pending_messages"):
            data["pending_messages"] = None

        # Ensure interrupted_at is None if empty
        if data.get("interrupted_at") == "":
            data["interrupted_at"] = None

        return await super().edit(request, pk, data)

    def can_create(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("updated_at", True)]
    searchable_fields = ["user_qiao_id", "instance_qiao_id"]
    sortable_fields = [
        "user_qiao_id",
        "instance_qiao_id",
        "interrupted_at",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField(
            "user_qiao_id",
            label="User Qiao ID",
            help_text="User external ID (primary key)",
        ),
        StringField(
            "instance_qiao_id",
            label="Instance Qiao ID",
            help_text="Instance external ID (primary key)",
        ),
        JSONField(
            "pending_messages",
            label="Pending Messages",
            help_text='Pending messages structure: {"outgoing": [...], "followup": [...], "total_pending": N}',
        ),
        LocalDateTimeField(
            "interrupted_at",
            label="Interrupted At",
            help_text="Timestamp when the last interruption occurred",
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="State creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


# Create view instances
ai_message_buffer_view = AIMessageBufferView(
    AIMessageBuffer,
    name="Message Buffers",
    label="Message Buffers",
    icon="fa fa-inbox",
    identity="ai_message_buffer",
)

ai_conversation_item_view = AIConversationItemView(
    AIConversationItem,
    name="Conversation Items",
    label="Conversation Items",
    icon="fa fa-comments",
    identity="ai_conversation_item",
)

ai_conversation_item_archive_view = AIConversationItemArchiveView(
    AIConversationItemArchive,
    name="Conversation Archives",
    label="Conversation Archives",
    icon="fa fa-archive",
    identity="ai_conversation_item_archive",
)

ai_conversation_state_view = AIConversationStateView(
    AIConversationState,
    name="Conversation State",
    label="Conversation State",
    icon="fa fa-exchange-alt",
    identity="ai_conversation_state",
)

# Export conversation views
AI_CONVERSATION_VIEWS = [
    ai_conversation_state_view,
    ai_message_buffer_view,
    ai_conversation_item_view,
    ai_conversation_item_archive_view,
]

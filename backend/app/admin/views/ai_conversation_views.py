"""
AI Conversation admin views.

This module contains Starlette-Admin views for AI conversation management
(message buffer, conversation items, and archives).
"""

from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import IntegerField, StringField, TextAreaField, BooleanField, JSONField

from models.ai.character import AIMessageBuffer, AIConversationItem, AIConversationItemArchive
from admin.views.base import IntegerEnumField
from admin.fields import LocalDateTimeField
from enums import AIMessageBufferState


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

    def can_create(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["id", "user_qiao_id", "character_qiao_id"]
    sortable_fields = [
        "id",
        "user_qiao_id",
        "character_qiao_id",
        "aggregate_state",
        "message_count",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="Buffer ID", help_text="Internal buffer ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external ID"),
        StringField("character_qiao_id", label="Character Qiao ID", help_text="Character external ID"),
        IntegerEnumField(
            "aggregate_state",
            enum=AIMessageBufferState,
            label="State",
            help_text="Buffer state: OPEN/LOCKED/COMPLETE/CANCELLED",
        ),
        StringField("micro_expires_at_ms", label="Micro Timer (ms)", help_text="Micro timer expiration timestamp"),
        StringField("macro_expires_at_ms", label="Macro Timer (ms)", help_text="Macro timer expiration timestamp"),
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
        IntegerField("message_count", label="Message Count", help_text="Number of messages in buffer"),
        StringField(
            "last_msg_time_ms",
            label="Last Message Time (ms)",
            help_text="Timestamp of last message appended to buffer",
        ),
        LocalDateTimeField("locked_at", label="Locked At", help_text="Timestamp when buffer entered LOCKED state"),
        LocalDateTimeField("created_at", label="Created At", help_text="Buffer creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


class AIConversationItemView(ModelView):
    """AI Conversation Item view - conversation history with Responses API blocks."""

    exclude_fields_from_create = [
        "id",
        "created_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "user_qiao_id",
        "character_qiao_id",
        "role",
        "buffer_id",
        "created_at",
    ]
    exclude_fields_from_list = [
        "content",
        "client_msg_ids",
    ]

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["id", "user_qiao_id", "character_qiao_id", "role", "content_preview", "response_id"]
    sortable_fields = [
        "id",
        "user_qiao_id",
        "character_qiao_id",
        "role",
        "buffer_id",
        "llm_config_id",
        "response_id",
        "is_excluded_from_context",
        "created_at",
    ]

    fields = [
        StringField("id", label="Item ID", help_text="Internal conversation item ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external ID"),
        StringField("character_qiao_id", label="Character Qiao ID", help_text="Character external ID"),
        StringField("role", label="Role", help_text="Message role: system/user/assistant"),
        JSONField("content", label="Content", help_text="Responses API content blocks array (JSONB)"),
        TextAreaField("content_preview", label="Content Preview", help_text="Text preview for admin display"),
        JSONField("client_msg_ids", label="Client Message IDs", help_text="Client message IDs merged into this row"),
        StringField("buffer_id", label="Buffer ID", help_text="Associated buffer ID (user role only)"),
        IntegerField("llm_config_id", label="LLM Config ID", help_text="LLM configuration used (assistant only)"),
        StringField("response_id", label="Response ID", help_text="Provider response identifier (assistant only)"),
        BooleanField(
            "is_excluded_from_context",
            label="Excluded from Context",
            help_text="Flag to exclude from LLM context (prompt injection, etc.)",
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Item creation time"),
    ]


class AIConversationItemArchiveView(ModelView):
    """AI Conversation Item Archive view - archived conversation history."""

    exclude_fields_from_create = [
        "id",
        "user_qiao_id",
        "character_qiao_id",
        "role",
        "content",
        "content_preview",
        "client_msg_ids",
        "buffer_id",
        "llm_config_id",
        "response_id",
        "is_excluded_from_context",
        "created_at",
        "archived_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "user_qiao_id",
        "character_qiao_id",
        "role",
        "content",
        "content_preview",
        "client_msg_ids",
        "buffer_id",
        "llm_config_id",
        "response_id",
        "is_excluded_from_context",
        "created_at",
        "archived_at",
    ]
    exclude_fields_from_list = [
        "content",
        "client_msg_ids",
    ]

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("archived_at", True)]
    searchable_fields = ["id", "user_qiao_id", "character_qiao_id", "role", "content_preview", "response_id"]
    sortable_fields = [
        "id",
        "user_qiao_id",
        "character_qiao_id",
        "role",
        "buffer_id",
        "llm_config_id",
        "response_id",
        "is_excluded_from_context",
        "created_at",
        "archived_at",
    ]

    fields = [
        StringField("id", label="Item ID", help_text="Internal conversation item ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external ID"),
        StringField("character_qiao_id", label="Character Qiao ID", help_text="Character external ID"),
        StringField("role", label="Role", help_text="Message role: system/user/assistant"),
        JSONField("content", label="Content", help_text="Responses API content blocks array (JSONB)"),
        TextAreaField("content_preview", label="Content Preview", help_text="Text preview for admin display"),
        JSONField("client_msg_ids", label="Client Message IDs", help_text="Client message IDs merged into this row"),
        StringField("buffer_id", label="Buffer ID", help_text="Associated buffer ID (user role only)"),
        IntegerField("llm_config_id", label="LLM Config ID", help_text="LLM configuration used (assistant only)"),
        StringField("response_id", label="Response ID", help_text="Provider response identifier (assistant only)"),
        BooleanField(
            "is_excluded_from_context",
            label="Excluded from Context",
            help_text="Flag to exclude from LLM context (prompt injection, etc.)",
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Original creation time"),
        LocalDateTimeField("archived_at", label="Archived At", help_text="Archive timestamp"),
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

# Export conversation views
AI_CONVERSATION_VIEWS = [
    ai_message_buffer_view,
    ai_conversation_item_view,
    ai_conversation_item_archive_view,
]

"""
AI Context admin views.

This module contains Starlette-Admin views for AI conversation context management.
"""

from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import StringField, IntegerField, TextAreaField

from models.ai import AIContext, AIContextArchive
from admin.views.base import IntegerEnumField
from admin.fields import LocalDateTimeField
from enums import AIContextRole, AIAggregateState


class AIContextView(ModelView):
    """Enhanced AI Context view for conversation context management."""

    label = "Contexts"
    name = "AI Contexts"

    exclude_fields_from_create = ["id", "character_id", "user_id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "character_id", "user_id", "created_at", "updated_at"]
    exclude_fields_from_list = []

    # Read-only view for AI contexts (mainly for monitoring)
    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["id", "character_id", "character_qiao_id", "user_id", "user_qiao_id"]
    sortable_fields = [
        "id",
        "character_qiao_id",
        "user_qiao_id",
        "role",
        "token_count",
        "aggregate_state",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal context ID"),
        StringField("character_id", label="Character ID", help_text="Character snowflake ID"),
        StringField(
            "character_qiao_id", label="Character Qiao ID", help_text="Character external identifier"
        ),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external identifier"),
        IntegerEnumField(
            "role",
            enum=AIContextRole,
            label="Role",
            help_text="Message role in conversation",
        ),
        TextAreaField("content", label="Content", help_text="Message content"),
        StringField("first_msg_id_client", label="First Msg ID", help_text="First message client ID"),
        StringField("last_msg_id_client", label="Last Msg ID", help_text="Last message client ID"),
        IntegerField("token_count", label="Token Count", help_text="Token count for this message"),
        IntegerEnumField(
            "is_attack",
            choices=[(0, "No"), (1, "Yes")],
            label="Is Attack",
            help_text="Whether this is an attack message",
        ),
        IntegerField("last_msg_time_ms", label="Last Msg Time", help_text="Last message time (ms)"),
        IntegerField(
            "buffer_expires_at_ms", label="Buffer Expires", help_text="Buffer expiration time (ms)"
        ),
        IntegerEnumField(
            "aggregate_state",
            enum=AIAggregateState,
            label="Aggregate State",
            help_text="Aggregate state",
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Context creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


class AIContextArchiveView(ModelView):
    """AI Context Archive view for viewing archived conversation contexts."""

    label = "Context Archives"
    name = "Context Archives"

    # Read-only view
    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    exclude_fields_from_create = ["id", "character_id", "user_id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "character_id", "user_id", "created_at", "updated_at"]
    exclude_fields_from_list = []

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["id", "character_id", "character_qiao_id", "user_id", "user_qiao_id"]
    sortable_fields = [
        "id",
        "character_qiao_id",
        "user_qiao_id",
        "role",
        "token_count",
        "aggregate_state",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal context ID"),
        StringField("character_id", label="Character ID", help_text="Character snowflake ID"),
        StringField(
            "character_qiao_id", label="Character Qiao ID", help_text="Character external identifier"
        ),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external identifier"),
        IntegerEnumField(
            "role",
            enum=AIContextRole,
            label="Role",
            help_text="Message role in conversation",
        ),
        TextAreaField("content", label="Content", help_text="Message content"),
        StringField("first_msg_id_client", label="First Msg ID", help_text="First message client ID"),
        StringField("last_msg_id_client", label="Last Msg ID", help_text="Last message client ID"),
        IntegerField("token_count", label="Token Count", help_text="Token count for this message"),
        IntegerEnumField(
            "is_attack",
            choices=[(0, "No"), (1, "Yes")],
            label="Is Attack",
            help_text="Whether this is an attack message",
        ),
        IntegerField("last_msg_time_ms", label="Last Msg Time", help_text="Last message time (ms)"),
        IntegerField(
            "buffer_expires_at_ms", label="Buffer Expires", help_text="Buffer expiration time (ms)"
        ),
        IntegerEnumField(
            "aggregate_state",
            enum=AIAggregateState,
            label="Aggregate State",
            help_text="Aggregate state",
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Context creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


# Create view instances
ai_context_view = AIContextView(AIContext, name="AI Contexts", icon="fa fa-comments", identity="ai_context")

ai_context_archive_view = AIContextArchiveView(
    AIContextArchive, name="Context Archives", icon="fa fa-archive", identity="ai_context_archive"
)

# Export context views
AI_CONTEXT_VIEWS = [
    ai_context_view,
    ai_context_archive_view,
]

"""AI Log admin views.

This module contains Starlette-Admin views for AI request logging.
"""

from typing import ClassVar

from starlette.requests import Request
from starlette_admin import BooleanField, DateTimeField, HasOne, IntegerField, StringField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.fields import JSONField

from app.admin.views.base import IntegerEnumField
from app.enums import AIRequestStatus
from app.models.ai.log import AIRequestLog


class AIRequestLogView(ModelView):
    """Enhanced AI Request Log view - read-only for monitoring."""

    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "instance_id",
        "user_id",
        "style_id",
        "personality_id",
        "llm_config_id",
        "response_id",
        "cache_hit",
        "buffer_id",
        "request",
        "response",
        "status",
        "token_count",
        "response_time",
        "created_at",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "instance_id",
        "user_id",
        "style_id",
        "personality_id",
        "llm_config_id",
        "response_id",
        "cache_hit",
        "buffer_id",
        "request",
        "response",
        "status",
        "token_count",
        "response_time",
        "created_at",
    ]
    exclude_fields_from_list: ClassVar[list[str]] = ["request", "response"]
    exclude_fields_from_detail: ClassVar[list[str]] = []  # Show all fields in detail view

    def can_create(self, request: Request) -> bool:
        _ = request
        return False

    def can_edit(self, request: Request) -> bool:
        _ = request
        return False

    def can_delete(self, request: Request) -> bool:
        _ = request
        return False

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = [
        "id",
        "instance_id",
        "user_id",
        "user_qiao_id",
        "provider_name",
        "model_name",
        "response_id",
        "buffer_id",
    ]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "instance_id",
        "user_id",
        "request_type",
        "status",
        "token_count",
        "response_time",
        "created_at",
        "completed_at",
    ]

    fields: ClassVar[list[object]] = [
        StringField("id", label="ID", help_text="Internal request log ID"),
        HasOne(
            "instance",
            identity="ai_instance",
            label="AI Instance",
            help_text="AI instance for this request",
            required=False,
        ),
        HasOne(
            "user",
            identity="user",
            label="User",
            help_text="User for this request",
            required=False,
        ),
        StringField(
            "user_qiao_id",
            label="User Qiao ID",
            help_text="User external qiao_id identifier",
        ),
        HasOne(
            "style",
            identity="ai_style",
            label="AI Style",
            help_text="Style used in this request",
            required=False,
        ),
        HasOne(
            "personality",
            identity="ai_personality",
            label="AI Personality",
            help_text="Personality used in this request",
            required=False,
        ),
        StringField("request_type", label="Request Type", help_text="production or test"),
        StringField("provider_name", label="Provider", help_text="LLM provider name"),
        StringField("model_name", label="Model", help_text="Model name used"),
        HasOne(
            "llm_config",
            identity="llm_config",
            label="LLM Config",
            help_text="LLM config used in this request",
            required=False,
        ),
        StringField("response_id", label="Response ID", help_text="Provider response identifier"),
        BooleanField("cache_hit", label="Cache Hit"),
        HasOne(
            "buffer",
            identity="ai_message_buffer",
            label="Message Buffer",
            help_text="Associated buffer that triggered the request",
            required=False,
        ),
        JSONField("request", label="Request", help_text="Request content in JSON format"),
        JSONField("response", label="Response", help_text="Response content in JSON format"),
        IntegerEnumField("status", enum=AIRequestStatus, label="Status"),
        IntegerField("token_count", label="Token Count"),
        IntegerField("response_time", label="Response Time (ms)"),
        DateTimeField("created_at", label="Created At", help_text="Request creation time"),
        DateTimeField("completed_at", label="Completed At", help_text="Request completion time"),
    ]


# Create view instance
ai_request_log_view = AIRequestLogView(
    AIRequestLog,
    name="AI Request Logs",
    label="Request Logs",
    icon="fa fa-history",
    identity="ai_request_log",
)

# Export log views
AI_LOG_VIEWS = [
    ai_request_log_view,
]

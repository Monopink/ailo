"""AI Log admin views.

This module contains Starlette-Admin views for AI request logging.
"""

from typing import ClassVar

from starlette.requests import Request
from starlette_admin import BooleanField, IntegerField, StringField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.fields import JSONField

from app.admin.fields import LocalDateTimeField
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
        StringField("instance_id", label="AI Instance ID", help_text="AI instance snowflake ID"),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        StringField(
            "user_qiao_id",
            label="User Qiao ID",
            help_text="User external qiao_id identifier",
        ),
        IntegerField("style_id", label="AI Style ID"),
        IntegerField("personality_id", label="AI Personality ID"),
        StringField("request_type", label="Request Type", help_text="production or test"),
        StringField("provider_name", label="Provider", help_text="LLM provider name"),
        StringField("model_name", label="Model", help_text="Model name used"),
        IntegerField("llm_config_id", label="LLM Config ID"),
        StringField("response_id", label="Response ID", help_text="Provider response identifier"),
        BooleanField("cache_hit", label="Cache Hit"),
        StringField(
            "buffer_id",
            label="Buffer ID",
            help_text="Associated buffer that triggered the request",
        ),
        JSONField("request", label="Request", help_text="Request content in JSON format"),
        JSONField("response", label="Response", help_text="Response content in JSON format"),
        IntegerEnumField("status", enum=AIRequestStatus, label="Status"),
        IntegerField("token_count", label="Token Count"),
        IntegerField("response_time", label="Response Time (ms)"),
        LocalDateTimeField("created_at", label="Created At", help_text="Request creation time"),
        LocalDateTimeField(
            "completed_at", label="Completed At", help_text="Request completion time"
        ),
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

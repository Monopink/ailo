"""
LLM (Large Language Model) related admin views.

This module contains Starlette-Admin views for managing LLM providers and configurations.
"""

import json
from typing import Dict, Any
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import EnumField, StringField, IntegerField, FloatField, JSONField, TextAreaField
from starlette_admin.actions import link_row_action
from starlette_admin.exceptions import FormValidationError
from models.llm import LLMProvider, LLMConfig, LLMTestLog


class ChineseJSONField(TextAreaField):
    """Custom field that displays JSON with Chinese characters properly in detail view."""

    async def serialize_value(self, request: Request, value: Any, action: str) -> Any:
        """Serialize value with ensure_ascii=False to display Chinese characters."""
        if value is None:
            return None

        # Convert dict to formatted JSON string with Chinese characters
        # This ensures Chinese characters are displayed properly in all views
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2)

        # If already a string, return as is
        return value


class LLMProviderView(ModelView):
    """Enhanced LLM Provider view with proper field configuration."""

    label = "Providers"
    name = "Providers"

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    fields_default_sort = [("name", False)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "created_at"]

    def can_delete(self, request: Request) -> bool:
        """Disable delete action for LLM providers."""
        return False

    fields = [
        StringField("id", label="ID", help_text="Internal provider ID"),
        EnumField(
            "name",
            choices=[("doubao", "Doubao"), ("mock", "Mock (Testing)")],
            label="Provider Name",
            help_text="LLM provider name",
            required=True,
        ),
        StringField("display_name", label="Display Name", help_text="Display name for UI", required=True),
        StringField("base_url", label="Base URL", help_text="API base URL", required=True),
        StringField(
            "api_key_env",
            label="API Key Environment Variable",
            help_text="Environment variable name for API key",
            required=True,
        ),
        StringField("default_model", label="Default Model", help_text="Default model name", required=True),
        IntegerField(
            "supports_streaming",
            label="Supports Streaming",
            help_text="Supports streaming output: 0=No, 1=Yes",
            required=True,
        ),
        IntegerField(
            "supports_json_schema",
            label="Supports JSON Schema",
            help_text="Supports JSON schema: 0=No, 1=Yes",
            required=True,
        ),
        IntegerField(
            "supports_thinking",
            label="Supports Thinking",
            help_text="Supports thinking mode: 0=No, 1=Yes",
            required=True,
        ),
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Custom validation to prevent duplicate provider names and handle data conversion."""
        errors: Dict[str | int, Any] = {}

        # Convert string values to integers for integer database fields
        # (status field removed from LLMProvider model)

        # Check if provider name already exists (for create operation)
        if request.url.path.endswith("/create") and data.get("name") == "doubao":
            # Check if doubao already exists in database
            from sqlalchemy import select
            from core.database import SessionLocal

            async with SessionLocal() as session:
                result = await session.execute(select(LLMProvider).where(LLMProvider.name == "doubao"))
                existing_provider = result.scalar_one_or_none()

                if existing_provider:
                    errors["name"] = "Doubao provider already exists. Only one Doubao provider is allowed."

        if len(errors) > 0:
            raise FormValidationError(errors)

        return await super().validate(request, data)


class LLMConfigView(ModelView):
    """Enhanced LLM Configuration view with proper field configuration."""

    label = "Configs"
    name = "Configs"

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    fields_default_sort = [("config_key", False)]
    searchable_fields = ["config_key", "model_name"]
    sortable_fields = ["id", "config_key", "model_name", "status", "priority", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal config ID"),
        EnumField(
            "provider_id",
            choices=[(1, "Doubao"), (99, "Mock (Testing)")],
            label="Provider",
            help_text="Select LLM provider",
            required=True,
        ),
        StringField(
            "config_key",
            label="Configuration Key",
            help_text="Configuration key (primary, backup, test, etc.)",
            required=True,
        ),
        StringField("model_name", label="Model Name", help_text="Specific model name (optional)"),
        FloatField("temperature", label="Temperature", help_text="Temperature parameter (0.0-2.0)"),
        IntegerField("max_tokens", label="Max Tokens", help_text="Maximum tokens"),
        IntegerField(
            "timeout_seconds", label="Timeout (seconds)", help_text="Timeout in seconds", required=True
        ),
        IntegerField("max_retries", label="Max Retries", help_text="Maximum retry attempts", required=True),
        IntegerField(
            "enable_streaming",
            label="Enable Streaming",
            help_text="Enable streaming output: 0=No, 1=Yes",
            required=True,
        ),
        IntegerField(
            "enable_thinking",
            label="Enable Thinking",
            help_text="Enable thinking mode: 0=No, 1=Yes",
            required=True,
        ),
        EnumField(
            "json_schema_mode",
            choices=[("auto", "Auto"), ("strict", "Strict"), ("disabled", "Disabled")],
            label="JSON Schema Mode",
            help_text="JSON schema mode",
            required=True,
        ),
        EnumField(
            "status",
            choices=[(1, "Active"), (2, "Inactive")],
            label="Status",
            help_text="Configuration status",
            required=True,
        ),
        IntegerField(
            "priority",
            label="Priority",
            help_text="Priority for failover (lower number = higher priority)",
            required=True,
        ),
        JSONField(
            "extra_params",
            label="Extra Parameters",
            help_text="Additional configuration parameters in JSON format (optional)",
        ),
    ]

    row_actions = ["view", "edit", "delete", "test_config"]

    @link_row_action(
        name="test_config",
        text="Test Config",
        icon_class="fas fa-flask",
    )
    def test_config_row_action(self, request, pk):
        """Custom row action to test this LLM configuration."""
        # Redirect to test interface with config_id parameter
        return f"/qiao-dash/llm-config-test?config_id={pk}"

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Custom validation and data conversion."""
        # Convert string values to integers for integer database fields
        if "provider_id" in data and isinstance(data["provider_id"], str):
            data["provider_id"] = int(data["provider_id"])
        # Note: status field removed from LLMConfig model

        return await super().validate(request, data)


# Create view instances
llm_provider_view = LLMProviderView(
    LLMProvider, name="Providers", icon="fa fa-server", identity="llm_provider"
)

llm_config_view = LLMConfigView(LLMConfig, name="Configs", icon="fa fa-cogs", identity="llm_config")


class LLMTestLogView(ModelView):
    """LLM Test Log view for viewing test execution records."""

    label = "Test Logs"
    name = "Test Logs"

    # Read-only view - exclude all fields from create/edit to disable these actions
    exclude_fields_from_create = [
        "id",
        "config_id",
        "config_key",
        "provider_name",
        "model_name",
        "test_message",
        "override_temperature",
        "override_max_tokens",
        "enable_thinking",
        "request",
        "response",
        "status",
        "error_message",
        "response_time_ms",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "reasoning_content",
        "created_at",
        "completed_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "config_id",
        "config_key",
        "provider_name",
        "model_name",
        "test_message",
        "override_temperature",
        "override_max_tokens",
        "enable_thinking",
        "request",
        "response",
        "status",
        "error_message",
        "response_time_ms",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "reasoning_content",
        "created_at",
        "completed_at",
    ]
    exclude_fields_from_list = ["request", "response"]
    exclude_fields_from_detail = []

    fields_default_sort = [("created_at", True)]  # Newest first
    searchable_fields = ["config_key", "provider_name", "model_name", "test_message"]
    sortable_fields = ["id", "config_id", "created_at", "status", "response_time_ms"]

    def can_create(self, request: Request) -> bool:
        """Disable create action for test logs - logs are created automatically."""
        return False

    def can_edit(self, request: Request) -> bool:
        """Disable edit action for test logs - logs are immutable."""
        return False

    def can_delete(self, request: Request) -> bool:
        """Disable delete action for test logs."""
        return False

    fields = [
        IntegerField("id", label="ID", help_text="Test log ID"),
        IntegerField("config_id", label="Config ID", help_text="LLM configuration ID"),
        StringField("config_key", label="Config Key", help_text="Configuration key"),
        StringField("provider_name", label="Provider", help_text="LLM provider name"),
        StringField("model_name", label="Model", help_text="Model name"),
        StringField("test_message", label="Test Message", help_text="Test message sent"),
        FloatField(
            "override_temperature", label="Override Temperature", help_text="Overridden temperature value"
        ),
        IntegerField(
            "override_max_tokens", label="Override Max Tokens", help_text="Overridden max tokens value"
        ),
        EnumField(
            "enable_thinking",
            choices=[(0, "No"), (1, "Yes")],
            label="Enable Thinking",
            help_text="Thinking mode enabled",
        ),
        ChineseJSONField("request", label="Request", help_text="Full request payload"),
        ChineseJSONField("response", label="Response", help_text="Full response data"),
        EnumField(
            "status",
            choices=[(1, "Success"), (2, "Failed"), (3, "Timeout")],
            label="Status",
            help_text="Test execution status",
        ),
        StringField("error_message", label="Error Message", help_text="Error message if failed"),
        IntegerField(
            "response_time_ms", label="Response Time (ms)", help_text="Response time in milliseconds"
        ),
        IntegerField("prompt_tokens", label="Prompt Tokens", help_text="Number of prompt tokens"),
        IntegerField(
            "completion_tokens", label="Completion Tokens", help_text="Number of completion tokens"
        ),
        IntegerField("total_tokens", label="Total Tokens", help_text="Total tokens used"),
        StringField("reasoning_content", label="Reasoning Content", help_text="Thinking/reasoning content"),
    ]


llm_test_log_view = LLMTestLogView(
    LLMTestLog, name="Test Logs", icon="fa fa-flask", identity="llm_test_log"
)

# Export views
LLM_MODEL_VIEWS = [
    llm_provider_view,
    llm_config_view,
    llm_test_log_view,
]

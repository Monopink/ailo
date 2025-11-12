"""
LLM (Large Language Model) related admin views.

This module contains Starlette-Admin views for managing LLM providers and configurations.
"""

from typing import Dict, Any
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import StringField, IntegerField, FloatField, JSONField, HasOne, EnumField
from starlette_admin.actions import link_row_action, row_action
from starlette_admin.exceptions import FormValidationError
from admin.views.base import IntegerEnumField
from admin.fields import LocalDateTimeField
from models.llm import LLMProvider, LLMConfig, LLMTestLog


class LLMProviderView(ModelView):
    """Enhanced LLM Provider view with proper field configuration."""

    label = "Providers"
    name = "Providers"

    exclude_fields_from_create = [
        "id",
        "created_at",
        "updated_at",
        "supports_streaming_display",
        "supports_json_schema_display",
        "supports_thinking_display",
    ]
    exclude_fields_from_edit = [
        "id",
        "created_at",
        "updated_at",
        "supports_streaming_display",
        "supports_json_schema_display",
        "supports_thinking_display",
    ]
    exclude_fields_from_list = []
    exclude_fields_from_detail = []

    fields_default_sort = [("display_name", False)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "created_at", "updated_at"]

    def can_delete(self, request: Request) -> bool:
        """Disable delete action for LLM providers."""
        return False

    fields = [
        StringField("id", label="ID", help_text="Internal provider ID"),
        EnumField(
            "name",
            choices=[
                ("doubao", "doubao"),
                ("mock", "mock"),
            ],
            label="Provider Name",
            help_text="LLM provider name (only doubao and mock are currently supported)",
            required=True,
        ),
        StringField(
            "display_name",
            label="Display Name",
            help_text="Display name for UI (must be unique)",
            required=True,
        ),
        StringField(
            "api_key_env",
            label="API Key Environment Variable",
            help_text="Environment variable name for API key (optional, defaults to {NAME}_API_KEY)",
            required=False,
        ),
        StringField("base_url", label="Base URL", help_text="API base URL", required=False),
        StringField("default_model", label="Default Model", help_text="Default model name", required=False),
        StringField(
            "supports_streaming_display", label="Supports Streaming", help_text="Supports streaming output"
        ),
        StringField(
            "supports_json_schema_display", label="Supports JSON Schema", help_text="Supports JSON schema"
        ),
        StringField(
            "supports_thinking_display", label="Supports Thinking", help_text="Supports thinking mode"
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Provider creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Custom validation to prevent duplicate display names."""
        errors: Dict[str | int, Any] = {}

        # Check if display_name already exists
        if "display_name" in data:
            from sqlalchemy import select
            from core.database import SessionLocal

            async with SessionLocal() as session:
                # For create operation
                if request.url.path.endswith("/create"):
                    result = await session.execute(
                        select(LLMProvider).where(LLMProvider.display_name == data["display_name"])
                    )
                    existing_provider = result.scalar_one_or_none()

                    if existing_provider:
                        errors["display_name"] = (
                            f"Display name '{data['display_name']}' already exists. "
                            "Please use a unique display name."
                        )

                # For edit operation
                elif "/edit/" in request.url.path:
                    # Extract provider ID from URL
                    try:
                        provider_id = int(request.url.path.split("/edit/")[1].split("/")[0])

                        result = await session.execute(
                            select(LLMProvider).where(
                                LLMProvider.display_name == data["display_name"],
                                LLMProvider.id != provider_id,
                            )
                        )
                        existing_provider = result.scalar_one_or_none()

                        if existing_provider:
                            errors["display_name"] = (
                                f"Display name '{data['display_name']}' already exists. "
                                "Please use a unique display name."
                            )
                    except (ValueError, IndexError):
                        pass  # Invalid URL format, skip validation

        if len(errors) > 0:
            raise FormValidationError(errors)

        return await super().validate(request, data)


class LLMConfigView(ModelView):
    """Enhanced LLM Configuration view with proper field configuration."""

    label = "Configs"
    name = "Configs"

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    def is_active(self, request: Request) -> bool:
        """Check if current page is related to this model (including test page)."""
        # Standard identity check for list/edit/detail pages
        if request.path_params.get("identity", None) == self.identity:
            return True

        # Check for test page with exact identity match
        path = request.scope["path"]
        return f"/{self.identity}/test/" in path

    fields_default_sort = [("name", False)]
    searchable_fields = ["name", "model_name"]
    sortable_fields = ["id", "name", "model_name", "status", "priority", "created_at", "updated_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal config ID"),
        HasOne(
            "provider",
            identity="llm_provider",
            label="Provider",
            help_text="Select LLM provider",
            required=True,
        ),
        StringField(
            "name",
            label="Name",
            help_text="Configuration name (primary, backup, test, etc.)",
            required=True,
        ),
        StringField("model_name", label="Model Name", help_text="Specific model name (optional)"),
        FloatField("temperature", label="Temperature", help_text="Temperature parameter (0.0-2.0)"),
        IntegerField("max_tokens", label="Max Tokens", help_text="Maximum tokens"),
        IntegerField(
            "timeout_seconds", label="Timeout (seconds)", help_text="Timeout in seconds", required=True
        ),
        EnumField(
            "thinking_mode",
            choices=[
                ("enabled", "Enabled (Force On)"),
                ("disabled", "Disabled (Force Off)"),
                ("auto", "Auto (Let Model Decide)"),
            ],
            label="Thinking Mode",
            help_text="Thinking mode: enabled=force on, disabled=force off, auto=let model decide",
            required=True,
        ),
        FloatField("top_p", label="Top P", help_text="Nucleus sampling threshold (0.0-1.0)", required=True),
        FloatField(
            "frequency_penalty",
            label="Frequency Penalty",
            help_text="Frequency penalty (-2.0 to 2.0). Reduces repetition based on token frequency.",
            required=True,
        ),
        FloatField(
            "presence_penalty",
            label="Presence Penalty",
            help_text="Presence penalty (-2.0 to 2.0). Encourages new topics based on token presence.",
            required=True,
        ),
        JSONField(
            "stop_sequences",
            label="Stop Sequences",
            help_text='Stop sequences (max 4 strings). Model stops when encountering these strings. Example: ["再见", "拜拜"]',
        ),
        EnumField(
            "json_schema_mode",
            choices=[
                ("auto", "Auto (Not Verified)"),
                ("strict", "Strict (Verified Supported)"),
                ("disabled", "Disabled (Verified Not Supported)"),
            ],
            label="JSON Schema Mode",
            help_text=(
                "JSON Schema support status. "
                "This field is automatically updated after testing. "
                "strict=Verified supported (can be used for AI Character), "
                "disabled=Verified not supported (test only), "
                "auto=Not verified (please test first)"
            ),
            required=True,
        ),
        JSONField(
            "default_tools",
            label="Default Tools",
            help_text='Tool definitions sent with each request (e.g., [{"type": "web_search"}])',
        ),
        EnumField(
            "default_tool_choice",
            choices=[
                ("auto", "Auto"),
                ("none", "Never Use Tools"),
                ("required", "Always Use Tools"),
            ],
            label="Tool Choice",
            help_text="How the model decides whether to call tools",
            required=True,
        ),
        EnumField(
            "parallel_tool_calls",
            choices=[(True, "Enabled"), (False, "Disabled")],
            label="Parallel Tool Calls",
            help_text="Allow the provider to execute tool calls in parallel",
            required=True,
        ),
        IntegerField(
            "max_tool_calls",
            label="Max Tool Calls",
            help_text="Maximum number of tool calls per request",
            required=True,
        ),
        JSONField(
            "default_extra_headers",
            label="Default Extra Headers",
            help_text='JSON object of extra headers (e.g., {"ark-beta-web-search": "true"})',
        ),
        JSONField(
            "default_extra_query",
            label="Default Extra Query Params",
            help_text="JSON object of additional query parameters sent to the provider",
        ),
        IntegerEnumField(
            "enable_streaming",
            choices=[(0, "Disabled (Recommended)"), (1, "Enabled (Experimental)")],
            label="Enable Streaming",
            help_text="Enable streaming output (experimental, may have compatibility issues with Doubao)",
            required=True,
        ),
        IntegerEnumField(
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
            help_text='Provider-specific parameters (e.g., max_completion_tokens, service_tier). Example: {"max_completion_tokens": 32000}',
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Configuration creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    row_actions = ["view", "edit", "test_config", "test_json_schema"]

    @link_row_action(
        name="test_config",
        text="Test Config",
        icon_class="fas fa-flask",
    )
    def test_config_row_action(self, request, pk):
        """Custom row action to test this LLM configuration."""
        # Redirect to test interface with RESTful path
        return f"/qiao-dash/llm_config/test/{pk}"

    @row_action(
        name="test_json_schema",
        text="Test JSON Schema",
        icon_class="fas fa-sync",
        confirmation="Test JSON Schema compatibility for this configuration? This will automatically update the JSON Schema Mode field based on the result.",
        submit_btn_text="Run Test",
        submit_btn_class="btn-primary",
    )
    async def test_json_schema_action(self, request: Request, pk: Any) -> str:
        """Test JSON Schema compatibility and update json_schema_mode."""
        from core.database import SessionLocal
        from services.admin.testing.llm_json_schema import test_json_schema_compatibility

        async with SessionLocal() as session:
            result = await test_json_schema_compatibility(session, int(pk))

            # Build detailed message
            message = result["message"]

            # Add test log link if available
            if result.get("test_log_id"):
                message += f"\n\n📝 Test Log ID: {result['test_log_id']}"

            # Add response details for successful tests
            if result.get("success") and result.get("response"):
                message += f"\n\n📤 Response: {result['response'][:100]}..."

            # Add performance metrics
            if result.get("response_time_ms"):
                message += f"\n⏱️ Response Time: {result['response_time_ms']}ms"

            if result.get("usage"):
                usage = result["usage"]
                message += f"\n📊 Tokens: {usage.get('total_tokens', 'N/A')} (prompt: {usage.get('prompt_tokens', 'N/A')}, completion: {usage.get('completion_tokens', 'N/A')})"

            if result.get("model"):
                message += f"\n🤖 Model: {result['model']}"

            return message

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Custom validation."""
        # No custom validation needed for now
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
        "config_name",
        "provider_name",
        "model_name",
        "test_message",
        "override_temperature",
        "override_max_tokens",
        "thinking_mode",
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
        "config_name",
        "provider_name",
        "model_name",
        "test_message",
        "override_temperature",
        "override_max_tokens",
        "thinking_mode",
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
    exclude_fields_from_list = []
    exclude_fields_from_detail = []

    fields_default_sort = [("created_at", True)]  # Newest first
    searchable_fields = ["config_name", "provider_name", "model_name", "test_message"]
    sortable_fields = ["id", "config_id", "created_at", "completed_at", "status", "response_time_ms"]

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
        StringField("config_name", label="Config Name", help_text="Configuration name"),
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
            "thinking_mode",
            choices=[
                ("enabled", "Enabled"),
                ("disabled", "Disabled"),
                ("auto", "Auto"),
            ],
            label="Thinking Mode",
            help_text="Thinking mode used in test",
        ),
        IntegerEnumField(
            "enable_json_schema",
            choices=[(0, "No"), (1, "Yes")],
            label="Enable JSON Schema",
            help_text="JSON Schema mode enabled",
        ),
        JSONField("request", label="Request", help_text="Full request payload"),
        JSONField("response", label="Response", help_text="Full response data"),
        IntegerEnumField(
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
        LocalDateTimeField("created_at", label="Created At", help_text="Test execution time"),
        LocalDateTimeField("completed_at", label="Completed At", help_text="Test completion time"),
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

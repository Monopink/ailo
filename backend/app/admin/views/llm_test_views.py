"""LLM configuration testing views for admin panel.

This module provides admin interface for testing LLM configurations.
Following the architectural pattern of separating concerns:
- View layer: Request handling, validation, response formatting
- Service layer: Business logic orchestration
- No business logic in views!
"""

import json

from starlette.datastructures import FormData
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.core.database import get_sessionmaker
from app.services.admin.testing.llm_config import execute_llm_config_test
from app.services.llm.config import get_llm_config
from app.type_defs import JSONDict, JSONValue
from app.utils.form_helpers import FormFieldError, get_float_field, get_int_field, get_text_field
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="app/admin/templates")


class LLMConfigTestView(CustomView):
    """LLM Configuration Test interface.

    This view provides a testing interface for LLM configurations,
    allowing administrators to:
    1. View configuration details
    2. Send test messages
    3. Override parameters (temperature, max_tokens)
    4. Enable thinking mode (if supported)
    5. View detailed test results
    """

    def is_accessible(self, _request: Request) -> bool:
        """Allow access to this view."""
        return True

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the LLM config test interface.

        GET: Display test form with configuration details
        POST: Execute test and return results
        """
        # Handle POST requests (test execution)
        if request.method == "POST":
            return await self.handle_test_request(request)

        # Handle GET requests (render interface)
        try:
            # Get config_id from path parameters (required)
            config_id_str = request.path_params.get("id")
            if not config_id_str:
                return templates.TemplateResponse(
                    "custom_views/llm_config_test.html",
                    {
                        "request": request,
                        "error": "Configuration ID is required in URL path",
                        "page_title": "LLM Config Test - Error",
                    },
                )

            try:
                config_id = int(config_id_str)
            except (ValueError, TypeError) as e:
                logger.error("invalid_config_id", config_id=config_id_str, error=str(e))
                return templates.TemplateResponse(
                    "custom_views/llm_config_test.html",
                    {
                        "request": request,
                        "error": f"Invalid configuration ID: {config_id_str}",
                        "page_title": "LLM Config Test - Error",
                    },
                )

            session_factory = get_sessionmaker()
            async with session_factory() as db:
                # Get configuration details
                config_result = await get_llm_config(db, config_id=config_id)
                if not config_result:
                    return templates.TemplateResponse(
                        "custom_views/llm_config_test.html",
                        {
                            "request": request,
                            "error": "Configuration not found",
                            "page_title": "LLM Config Test - Error",
                        },
                    )

                config, provider = config_result

                # Prepare context for template - extract all data BEFORE leaving async context
                # NOTE: Use 'llm_config' instead of 'config' to avoid conflict with
                # starlette-admin's AdminConfig
                context = {
                    "request": request,
                    "config_id": config_id,
                    "llm_config": {
                        "name": config.name,
                        "provider_name": provider.display_name,
                        "model_name": config.model_name or provider.default_model,
                        "status": config.status,
                        "priority": config.priority,
                        "temperature": (
                            float(config.temperature) if config.temperature is not None else None
                        ),
                        "max_tokens": config.max_tokens,
                        "timeout_seconds": config.timeout_seconds,
                        "thinking_mode": config.thinking_mode,
                        "json_schema_mode": config.json_schema_mode,
                        "supports_thinking": bool(provider.supports_thinking),
                        "top_p": float(config.top_p) if config.top_p is not None else None,
                        "frequency_penalty": (
                            float(config.frequency_penalty)
                            if config.frequency_penalty is not None
                            else None
                        ),
                        "presence_penalty": (
                            float(config.presence_penalty)
                            if config.presence_penalty is not None
                            else None
                        ),
                        "stop_sequences": config.stop_sequences or [],
                        "stop_sequences_display": json.dumps(
                            config.stop_sequences or [], ensure_ascii=False
                        ),
                        "default_tools": config.default_tools or [],
                        "default_tools_display": json.dumps(
                            config.default_tools or [], ensure_ascii=False
                        ),
                        "default_tool_choice": config.default_tool_choice,
                        "parallel_tool_calls": config.parallel_tool_calls,
                        "max_tool_calls": config.max_tool_calls,
                        "default_extra_headers": config.default_extra_headers or {},
                        "default_extra_headers_display": json.dumps(
                            config.default_extra_headers or {}, ensure_ascii=False
                        ),
                        "default_extra_query": config.default_extra_query or {},
                        "default_extra_query_display": json.dumps(
                            config.default_extra_query or {}, ensure_ascii=False
                        ),
                        "enable_streaming": config.enable_streaming,
                        "extra_params": config.extra_params or {},
                        "extra_params_display": json.dumps(
                            config.extra_params or {}, ensure_ascii=False
                        ),
                    },
                    "page_title": f"Test LLM Config: {config.name}",
                }

            # Return response AFTER async context to ensure all data is extracted
            return templates.TemplateResponse("custom_views/llm_config_test.html", context)

        except Exception as e:
            logger.error("llm_config_test_render_failed", error=str(e), exc_info=True)
            return templates.TemplateResponse(
                "custom_views/llm_config_test.html",
                {
                    "request": request,
                    "error": f"Failed to load test interface: {e!s}",
                    "page_title": "LLM Config Test - Error",
                },
            )

    async def handle_test_request(self, request: Request) -> JSONResponse:
        """Handle test execution request.

        This method:
        1. Extracts and validates form data
        2. Calls service layer to execute test
        3. Returns JSON response with results

        No business logic here - all in service layer!
        """
        try:
            form_data = await request.form()

            # Extract and validate form data using type-safe helpers
            try:
                config_id = get_int_field(form_data, "config_id")
                test_message = get_text_field(form_data, "test_message")

                # Validate message content - moved outside try to avoid TRY301
                self._validate_test_message(test_message)

                # Optional parameters
                override_temperature = None
                if form_data.get("override_temperature_enabled") == "1":
                    override_temperature = get_float_field(form_data, "override_temperature")

                override_max_tokens = None
                if form_data.get("override_max_tokens_enabled") == "1":
                    override_max_tokens = get_int_field(form_data, "override_max_tokens")

                thinking_mode = form_data.get("thinking_mode")
                if thinking_mode not in ["enabled", "disabled", "auto"]:
                    thinking_mode = None  # Use config default

                # Parse request overrides
                request_overrides = self._parse_request_overrides(form_data)

            except FormFieldError as e:
                logger.warning("llm_config_test_form_validation_error", error=str(e))
                return JSONResponse({"success": False, "error": str(e)}, status_code=400)

            # Execute test using service layer
            session_factory = get_sessionmaker()
            async with session_factory() as db:
                result = await execute_llm_config_test(
                    db=db,
                    config_id=config_id,
                    test_message=test_message,
                    override_temperature=override_temperature,
                    override_max_tokens=override_max_tokens,
                    thinking_mode=thinking_mode,
                    request_overrides=request_overrides or None,
                )

                logger.info(
                    "llm_config_test_request_completed",
                    config_id=config_id,
                    success=result.get("success", False),
                )

                return JSONResponse(result)

        except Exception as e:
            logger.error("llm_config_test_request_failed", error=str(e), exc_info=True)
            return JSONResponse(
                {"success": False, "error": f"Test request failed: {e!s}"}, status_code=500
            )

    def _validate_test_message(self, test_message: str) -> None:
        """Validate test message is not empty."""
        if not test_message.strip():
            raise FormFieldError("Test message cannot be empty")

    def _parse_request_overrides(self, form_data: FormData) -> JSONDict:
        """Parse and validate request override parameters from form data."""
        request_overrides: JSONDict = {}

        # Parse JSON fields
        tools_json = self._parse_json_field(form_data, "tools_json", "Tools JSON", list)
        if tools_json is not None:
            request_overrides["tools"] = tools_json

        extra_headers = self._parse_json_field(
            form_data, "extra_headers_json", "Extra headers", dict
        )
        if extra_headers is not None:
            request_overrides["default_extra_headers"] = extra_headers

        extra_query = self._parse_json_field(
            form_data, "extra_query_json", "Extra query parameters", dict
        )
        if extra_query is not None:
            request_overrides["default_extra_query"] = extra_query

        extra_body = self._parse_json_field(form_data, "extra_body_json", "Extra body", dict)
        if extra_body is not None:
            request_overrides["extra_body"] = extra_body

        # Parse simple fields
        tool_choice_override = form_data.get("tool_choice_override")
        if tool_choice_override and tool_choice_override != "inherit":
            request_overrides["tool_choice"] = tool_choice_override

        max_tool_calls_override = form_data.get("max_tool_calls_override")
        if max_tool_calls_override:
            try:
                request_overrides["max_tool_calls"] = int(max_tool_calls_override)
            except ValueError as exc:
                raise FormFieldError(f"Max tool calls must be an integer: {exc!s}") from exc

        return request_overrides

    def _parse_json_field(
        self, form_data: FormData, field_name: str, label: str, expected_type: type | None
    ) -> JSONValue | None:
        """Parse and validate a JSON field from form data."""
        raw_value = form_data.get(field_name)
        if raw_value is None:
            return None
        raw_value = raw_value.strip()
        if not raw_value:
            return None

        try:
            parsed_value = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise FormFieldError(f"{label} must be valid JSON: {exc!s}") from exc

        if expected_type and not isinstance(parsed_value, expected_type):
            raise FormFieldError(f"{label} must be a {expected_type.__name__}")

        return parsed_value


# Create view instance
llm_config_test_view = LLMConfigTestView(
    label="LLM Config Test",
    icon="",
    path="/llm_config/test/{id:int}",
    methods=["GET", "POST"],
    add_to_menu=False,  # Accessed via row actions only
)

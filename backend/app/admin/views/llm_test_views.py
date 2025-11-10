"""
LLM configuration testing views for admin panel.

This module provides admin interface for testing LLM configurations.
Following the architectural pattern of separating concerns:
- View layer: Request handling, validation, response formatting
- Service layer: Business logic orchestration
- No business logic in views!
"""

import json

from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from core.database import SessionLocal
from services.admin.testing.llm_config import execute_llm_config_test
from services.llm.config import get_llm_config
from utils.logging import get_logger
from utils.form_helpers import get_int_field, get_text_field, get_float_field, FormFieldError

logger = get_logger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="admin/templates")


class LLMConfigTestView(CustomView):
    """
    LLM Configuration Test interface.

    This view provides a testing interface for LLM configurations,
    allowing administrators to:
    1. View configuration details
    2. Send test messages
    3. Override parameters (temperature, max_tokens)
    4. Enable thinking mode (if supported)
    5. View detailed test results
    """

    def is_accessible(self, request: Request) -> bool:
        """Allow access to this view."""
        return True

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """
        Render the LLM config test interface.

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

            async with SessionLocal() as db:
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
                # NOTE: Use 'llm_config' instead of 'config' to avoid conflict with starlette-admin's AdminConfig
                context = {
                    "request": request,
                    "config_id": config_id,
                    "llm_config": {
                        "name": config.name,
                        "provider_name": provider.display_name,
                        "model_name": config.model_name or provider.default_model,
                        "temperature": float(config.temperature) if config.temperature is not None else None,
                        "max_tokens": config.max_tokens,
                        "timeout_seconds": config.timeout_seconds,
                        "thinking_mode": config.thinking_mode,
                        "json_schema_mode": config.json_schema_mode,
                        "supports_thinking": bool(provider.supports_thinking),
                        "top_p": float(config.top_p) if config.top_p is not None else None,
                        "frequency_penalty": float(config.frequency_penalty)
                        if config.frequency_penalty is not None
                        else None,
                        "presence_penalty": float(config.presence_penalty)
                        if config.presence_penalty is not None
                        else None,
                        "stop_sequences": config.stop_sequences or [],
                        "stop_sequences_display": json.dumps(
                            config.stop_sequences or [], ensure_ascii=False
                        ),
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
                    "error": f"Failed to load test interface: {str(e)}",
                    "page_title": "LLM Config Test - Error",
                },
            )

    async def handle_test_request(self, request: Request) -> JSONResponse:
        """
        Handle test execution request.

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

                # Optional parameters
                override_temperature = None
                if "override_temperature" in form_data and form_data.get("override_temperature"):
                    override_temperature = get_float_field(form_data, "override_temperature")

                override_max_tokens = None
                if "override_max_tokens" in form_data and form_data.get("override_max_tokens"):
                    override_max_tokens = get_int_field(form_data, "override_max_tokens")

                # Get thinking_mode from form (enabled/disabled/auto)
                thinking_mode = form_data.get("thinking_mode")
                if thinking_mode not in ["enabled", "disabled", "auto"]:
                    thinking_mode = None  # Use config default

            except FormFieldError as e:
                logger.warning("llm_config_test_form_validation_error", error=str(e))
                return JSONResponse({"success": False, "error": str(e)}, status_code=400)

            # Validate message content
            if not test_message.strip():
                return JSONResponse(
                    {"success": False, "error": "Test message cannot be empty"}, status_code=400
                )

            # Execute test using service layer
            async with SessionLocal() as db:
                result = await execute_llm_config_test(
                    db=db,
                    config_id=config_id,
                    test_message=test_message,
                    override_temperature=override_temperature,
                    override_max_tokens=override_max_tokens,
                    thinking_mode=thinking_mode,
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
                {"success": False, "error": f"Test request failed: {str(e)}"}, status_code=500
            )


# Create view instance
llm_config_test_view = LLMConfigTestView(
    label="LLM Config Test",
    icon="",
    path="/llm_config/test/{id:int}",
    methods=["GET", "POST"],
    add_to_menu=False,  # Accessed via row actions only
)

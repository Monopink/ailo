"""
LLM configuration testing views for admin panel.

This module provides admin interface for testing LLM configurations.
Following the architectural pattern of separating concerns:
- View layer: Request handling, validation, response formatting
- Service layer: Business logic orchestration
- No business logic in views!
"""

from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from core.database import SessionLocal
from services.admin.llm_config_test import execute_llm_config_test
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
            # Get config_id from URL parameters (required)
            config_id_str = request.query_params.get("config_id")
            if not config_id_str:
                return templates.TemplateResponse(
                    "custom_views/llm_config_test.html",
                    {
                        "request": request,
                        "error": "Configuration ID is required in URL parameters",
                        "page_title": "LLM Config Test - Error",
                    },
                )

            try:
                config_id = int(config_id_str)
            except ValueError:
                return templates.TemplateResponse(
                    "custom_views/llm_config_test.html",
                    {
                        "request": request,
                        "error": "Invalid configuration ID format",
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

                # Prepare context for template
                context = {
                    "request": request,
                    "config_id": config_id,
                    "config": {
                        "config_key": config.config_key,
                        "provider_name": provider.display_name,
                        "model_name": config.model_name or provider.default_model,
                        "temperature": float(config.temperature) if config.temperature else None,
                        "max_tokens": config.max_tokens,
                        "timeout_seconds": config.timeout_seconds,
                        "enable_streaming": config.enable_streaming,
                        "enable_thinking": config.enable_thinking,
                        "json_schema_mode": config.json_schema_mode,
                        "supports_thinking": provider.supports_thinking,
                    },
                    "page_title": f"Test LLM Config: {config.config_key}",
                }

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

                enable_thinking = form_data.get("enable_thinking") == "1"

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
                    enable_thinking=enable_thinking,
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
    path="/llm-config-test",
    methods=["GET", "POST"],
    add_to_menu=False,  # Accessed via row actions only
)

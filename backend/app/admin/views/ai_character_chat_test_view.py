"""
AI Character Chat Test view for admin panel.

This module provides admin interface for testing AI character chat functionality
following the architectural patterns and prototype design specifications.
"""

from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from core.database import SessionLocal
from services.admin.ai_character_chat import ai_character_chat_test_service, AICharacterChatTestError
from utils.logging import get_logger
from utils.form_helpers import get_text_field, get_int_field, FormFieldError

logger = get_logger(__name__)

# Initialize templates with relative path
templates = Jinja2Templates(directory="admin/templates", auto_reload=True)


class AICharacterChatTestView(CustomView):
    """
    AI Character Chat Test interface following prototype design.

    Prototype Requirements:
    - Only includes: LLM Configuration dropdown + Test message input
    - No AI character selection (fixed via URL parameter)
    - No user selection (automatically matched)
    - Shows prerequisite validation status
    - Supports continuous testing with context preservation
    """

    def is_accessible(self, request: Request) -> bool:
        """Allow access to this view."""
        return True

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the AI character chat test interface according to prototype design."""

        # Check action parameter for API endpoints
        action = request.query_params.get("action")

        if action == "readiness":
            return await self.check_test_readiness(request)

        # Handle POST requests (test execution)
        if request.method == "POST":
            return await self.handle_test_request(request)

        # Default GET request - render the interface
        try:
            # Get character_id from path parameters (required)
            character_id_str = request.path_params.get("id")
            if not character_id_str:
                return templates.TemplateResponse(
                    "custom_views/ai_character_chat_test.html",
                    {
                        "request": request,
                        "error": "Character ID is required in URL path",
                        "page_title": "AI Character Chat Test - Error",
                    },
                )

            try:
                character_id = int(character_id_str)
            except (ValueError, TypeError) as e:
                logger.error("invalid_character_id", character_id=character_id_str, error=str(e))
                return templates.TemplateResponse(
                    "custom_views/ai_character_chat_test.html",
                    {
                        "request": request,
                        "error": f"Invalid character_id: {character_id_str}",
                        "page_title": "AI Character Chat Test - Error",
                    },
                )

            # Initialize context
            context = {
                "request": request,
                "character_id": character_id,
                "page_title": "AI Character Chat Test",
                "test_readiness": None,
                "llm_configs": [],
                "error": None,
            }

            async with SessionLocal() as db:
                # Check test readiness using the new service
                test_readiness = await ai_character_chat_test_service.validate_test_readiness(
                    db=db, character_id=character_id
                )
                context["test_readiness"] = test_readiness

                # Get available LLM configurations
                if test_readiness.get("ready", False):
                    context["llm_configs"] = test_readiness.get("available_llm_configs", [])

            return templates.TemplateResponse("custom_views/ai_character_chat_test.html", context)

        except Exception as e:
            logger.error("ai_character_chat_test_render_failed", error=str(e), exc_info=True)
            return templates.TemplateResponse(
                "custom_views/ai_character_chat_test.html",
                {
                    "request": request,
                    "error": f"Failed to load AI character chat test interface: {str(e)}",
                    "page_title": "AI Character Chat Test - Error",
                },
            )

    async def handle_test_request(self, request: Request) -> JSONResponse:
        """
        Handle AI character test request using the new unified service.

        This method leverages the facade service to execute the complete test flow:
        validation -> user matching -> execution (calling main logic).
        """
        try:
            # Parse request data with type-safe extraction
            form_data = await request.form()

            try:
                character_id = get_int_field(form_data, "character_id")
                llm_config_name = get_text_field(form_data, "llm_config_name")
                test_message = get_text_field(form_data, "test_message")
            except FormFieldError as e:
                return JSONResponse(
                    {"error": str(e)},
                    status_code=400,
                )

            # Validate message content
            if not test_message.strip():
                return JSONResponse(
                    {"error": "Test message cannot be empty"},
                    status_code=400,
                )

            async with SessionLocal() as db:
                # Use the unified facade service for complete test execution
                # Optional mock overrides
                mock_overrides = None
                raw_overrides = form_data.get("mock_overrides_json")
                if raw_overrides:
                    try:
                        import json

                        parsed = json.loads(raw_overrides)
                        if isinstance(parsed, dict):
                            mock_overrides = parsed
                    except Exception:
                        return JSONResponse({"error": "Invalid mock_overrides_json"}, status_code=400)

                # Persist switch (default ON)
                persist_raw = form_data.get("persist")
                persist_flag = True
                if persist_raw is not None:
                    val = str(persist_raw).strip().lower()
                    persist_flag = val in ("1", "true", "on", "yes")

                result = await ai_character_chat_test_service.prepare_and_execute_test(
                    db=db,
                    character_id=character_id,
                    llm_config_name=llm_config_name,
                    test_message=test_message,
                    mock_overrides=mock_overrides,
                    persist=persist_flag,
                )

                # Format response for frontend display
                test_execution = result["test_execution"]

                # Prefer latest scores after execution when available, and sanitize datetimes
                def _sanitize_scores(scores):
                    sanitized = []
                    if not scores:
                        return sanitized
                    for item in scores:
                        try:
                            row = dict(item)
                        except Exception:
                            row = item
                        for k in ("created_at", "updated_at"):
                            v = row.get(k)
                            try:
                                if hasattr(v, "isoformat"):
                                    row[k] = v.isoformat()
                            except Exception:
                                row[k] = str(v) if v is not None else None
                        sanitized.append(row)
                    return sanitized

                latest_scores = _sanitize_scores(
                    result.get("relationship_scores_after")
                ) or _sanitize_scores(result["validation_info"].get("relationship_scores"))

                response_data = {
                    "success": True,
                    "test_mode": test_execution["test_mode"],
                    "log_id": test_execution["log_id"],
                    "character_info": {
                        "qiao_id": result["validation_info"]["character"]["qiao_id"],
                        "category": result["validation_info"]["character"]["category"],
                        "style": result["validation_info"]["style"]["display_name"],
                        "personality": result["validation_info"]["personality"]["display_name"],
                    },
                    # Rich profile/settings for UI panels
                    "character_profile": result["validation_info"].get("character_profile"),
                    "style": result["validation_info"].get("style"),
                    "personality": result["validation_info"].get("personality"),
                    "character_settings": {
                        "memory": result["validation_info"]["character"].get("memory"),
                        "prompt_variables": result["validation_info"]["character"].get("prompt_variables"),
                    },
                    "test_user_info": {
                        "qiao_id": result["test_user_info"]["test_user"]["qiao_id"],
                        "username": result["test_user_info"]["test_user"]["username"],
                        "nickname": result["test_user_info"]["test_user_profile"]["nickname"],
                    },
                    "test_user_profile": result["test_user_info"].get("test_user_profile"),
                    "conversation": test_execution["conversation"],
                    "performance": test_execution["performance"],
                    "relationship_scores": latest_scores,
                    "request_payload": test_execution.get("request_payload"),
                    "selected_relationship_after": result.get("selected_relationship_after"),
                }

                logger.info(
                    "ai_character_test_completed_successfully",
                    character_id=character_id,
                    response_time_ms=test_execution["performance"]["response_time_ms"],
                    messages_count=len(test_execution["conversation"]["all_messages"]),
                )

                return JSONResponse(response_data)

        except FormFieldError as e:
            logger.error(
                "ai_character_test_form_validation_error",
                error=str(e),
            )
            return JSONResponse(
                {"success": False, "error": str(e)},
                status_code=400,
            )

        except AICharacterChatTestError as e:
            logger.error(
                "ai_character_test_service_error",
                error_code=e.error_code,
                error=str(e),
            )
            return JSONResponse(
                {
                    "success": False,
                    "error": e.message,
                    "error_code": e.error_code,
                    "suggestions": e.suggestions,
                },
                status_code=400,
            )

        except Exception as e:
            logger.error(
                "ai_character_test_request_failed",
                error=str(e),
                exc_info=True,
            )
            return JSONResponse(
                {"success": False, "error": f"Test request failed: {str(e)}"},
                status_code=500,
            )

    async def check_test_readiness(self, request: Request) -> JSONResponse:
        """API endpoint to check test readiness status."""
        try:
            character_id_str = request.path_params.get("id")
            if not character_id_str:
                return JSONResponse(
                    {"error": "Missing character_id in URL path"},
                    status_code=400,
                )

            try:
                character_id = int(character_id_str)
            except (ValueError, TypeError):
                return JSONResponse(
                    {"error": "Invalid character_id format"},
                    status_code=400,
                )

            async with SessionLocal() as db:
                readiness = await ai_character_chat_test_service.validate_test_readiness(
                    db=db, character_id=character_id
                )

                return JSONResponse(readiness)

        except Exception as e:
            logger.error(
                "test_readiness_check_failed",
                character_id=character_id_str,
                error=str(e),
            )
            return JSONResponse(
                {"error": f"Failed to check test readiness: {str(e)}"},
                status_code=500,
            )


# Create view instance
ai_character_chat_test_view = AICharacterChatTestView(
    label="Character Chat Test",
    icon="",
    path="/ai_character/chat-test/{id:int}",
    methods=["GET", "POST"],
    add_to_menu=False,  # Accessed via row actions only
)

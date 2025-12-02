"""
AI Instance Chat Test view for admin panel.

This module provides admin interface for testing AI instance chat functionality
following the architectural patterns and prototype design specifications.
"""

import json

from core.database import get_sessionmaker
from services.admin.testing.instance_chat import (
    AIInstanceChatTestError,
    ai_instance_chat_test_service,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView
from utils.form_helpers import FormFieldError, get_int_field, get_text_field
from utils.logging import get_logger

logger = get_logger(__name__)

# Initialize templates with relative path
templates = Jinja2Templates(directory="admin/templates", auto_reload=True)


class AIInstanceChatTestView(CustomView):
    """
    AI Instance Chat Test interface following prototype design.

    Prototype Requirements:
    - Only includes: LLM Configuration dropdown + Test message input
    - No AI instance selection (fixed via URL parameter)
    - No user selection (automatically matched)
    - Shows prerequisite validation status
    - Supports continuous testing with context preservation
    """

    def is_accessible(self, request: Request) -> bool:
        """Allow access to this view."""
        return True

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the AI instance chat test interface according to prototype design."""

        # Check action parameter for API endpoints
        action = request.query_params.get("action")

        if action == "readiness":
            return await self.check_test_readiness(request)

        if action == "archive":
            return await self.archive_conversations(request)

        # Handle POST requests (test execution)
        if request.method == "POST":
            return await self.handle_test_request(request)

        # Default GET request - render the interface
        try:
            # Get instance_id from path parameters (required)
            instance_id_str = request.path_params.get("id")
            if not instance_id_str:
                return templates.TemplateResponse(
                    "custom_views/ai_instance_chat_test.html",
                    {
                        "request": request,
                        "error": "URL 中缺少实例 ID",
                        "page_title": "AI 实例测试 - 错误",
                    },
                )

            try:
                instance_id = int(instance_id_str)
            except (ValueError, TypeError) as e:
                logger.error("invalid_instance_id", instance_id=instance_id_str, error=str(e))
                return templates.TemplateResponse(
                    "custom_views/ai_instance_chat_test.html",
                    {
                        "request": request,
                        "error": f"实例 ID 无效：{instance_id_str}",
                        "page_title": "AI 实例测试 - 错误",
                    },
                )

            # Initialize context
            context = {
                "request": request,
                "instance_id": instance_id,
                "page_title": "AI Instance Chat Test",
                "test_readiness": None,
                "llm_configs": [],
                "error": None,
            }

            session_factory = get_sessionmaker()
            async with session_factory() as db:
                # Check test readiness using the new service
                test_readiness = await ai_instance_chat_test_service.validate_test_readiness(
                    db=db, instance_id=instance_id
                )
                context["test_readiness"] = test_readiness

                # Get available LLM configurations
                if test_readiness.get("ready", False):
                    context["llm_configs"] = test_readiness.get("available_llm_configs", [])

            return templates.TemplateResponse("custom_views/ai_instance_chat_test.html", context)

        except Exception as e:
            logger.error("ai_instance_chat_test_render_failed", error=str(e), exc_info=True)
            return templates.TemplateResponse(
                "custom_views/ai_instance_chat_test.html",
                {
                    "request": request,
                    "error": f"加载测试页面失败：{e!s}",
                    "page_title": "AI 实例测试 - 错误",
                },
            )

    async def handle_test_request(self, request: Request) -> JSONResponse:
        """
        Handle AI instance test request using the new unified service.

        This method leverages the facade service to execute the complete test flow:
        validation -> user matching -> execution (calling main logic).
        """
        try:
            # Parse request data with type-safe extraction
            form_data = await request.form()

            try:
                instance_id = get_int_field(form_data, "instance_id")
                llm_config_name = get_text_field(form_data, "llm_config_name")
                test_message = get_text_field(form_data, "test_message")
            except FormFieldError as e:
                return JSONResponse({"error": f"字段校验失败：{e!s}"}, status_code=400)

            # Validate message content
            if not test_message.strip():
                return JSONResponse({"error": "测试信息不能为空"}, status_code=400)

            session_factory = get_sessionmaker()
            async with session_factory() as db:
                # Use the unified facade service for complete test execution
                # Optional mock overrides
                mock_overrides = None
                raw_overrides = form_data.get("mock_overrides_json")
                if raw_overrides:
                    try:
                        parsed = json.loads(raw_overrides)
                        if isinstance(parsed, dict):
                            mock_overrides = parsed
                    except Exception:
                        return JSONResponse(
                            {"error": "mock_overrides_json 不是合法 JSON"}, status_code=400
                        )

                # Persist switch (default ON)
                persist_raw = form_data.get("persist")
                persist_flag = True
                if persist_raw is not None:
                    val = str(persist_raw).strip().lower()
                    persist_flag = val in ("1", "true", "on", "yes")

                result = await ai_instance_chat_test_service.prepare_and_execute_test(
                    db=db,
                    instance_id=instance_id,
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
                validation_instance = result["validation_info"]["instance"]
                ai_type_info = validation_instance.get("ai_type")
                ai_type_display = (
                    ai_type_info.get("display_name") if isinstance(ai_type_info, dict) else None
                )

                response_data = {
                    "success": True,
                    "test_mode": test_execution["test_mode"],
                    "log_id": test_execution["log_id"],
                    "instance_info": {
                        "qiao_id": validation_instance.get("instance_qiao_id"),
                        "ai_type_display": ai_type_display,
                        "ai_type": ai_type_info,
                        "style": result["validation_info"]["style"]["display_name"],
                        "personality": result["validation_info"]["personality"]["display_name"],
                    },
                    # Rich profile/settings for UI panels
                    "instance_profile": result["validation_info"].get("instance_profile"),
                    "style": result["validation_info"].get("style"),
                    "personality": result["validation_info"].get("personality"),
                    "instance_settings": {
                        "memory": validation_instance.get("memory"),
                        "prompt_variables": validation_instance.get("prompt_variables"),
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
                    "history_messages": test_execution.get("history_messages", []),
                    "current_user_message": test_execution.get("current_user_message"),
                    "response_body": test_execution.get("response_body"),
                    "selected_relationship_after": result.get("selected_relationship_after"),
                }

                # Keep API contract identical to readiness endpoint so the frontend
                # can refresh test-user state without extra fetches.
                response_data["available_contacts"] = result.get("available_contacts", [])
                response_data["available_test_users"] = result.get("available_test_users", [])
                response_data["test_user_selection_locked"] = result.get(
                    "test_user_selection_locked", False
                )
                response_data["locked_test_user_qiao_id"] = result.get("locked_test_user_qiao_id")

                logger.info(
                    "ai_instance_test_completed_successfully",
                    instance_id=instance_id,
                    response_time_ms=test_execution["performance"]["response_time_ms"],
                    messages_count=len(test_execution["conversation"]["all_messages"]),
                )

                return JSONResponse(response_data)

        except FormFieldError as e:
            logger.error(
                "ai_instance_test_form_validation_error",
                error=str(e),
            )
            return JSONResponse(
                {"success": False, "error": f"字段校验失败：{e!s}"},
                status_code=400,
            )

        except AIInstanceChatTestError as e:
            logger.error(
                "ai_instance_test_service_error",
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
                "ai_instance_test_request_failed",
                error=str(e),
                exc_info=True,
            )
            return JSONResponse(
                {"success": False, "error": f"测试请求异常：{e!s}"},
                status_code=500,
            )

    async def check_test_readiness(self, request: Request) -> JSONResponse:
        """API endpoint to check test readiness status."""
        try:
            instance_id_str = request.path_params.get("id")
            if not instance_id_str:
                return JSONResponse({"error": "URL 中缺少实例 ID"}, status_code=400)

            try:
                instance_id = int(instance_id_str)
            except (ValueError, TypeError):
                return JSONResponse({"error": "实例 ID 格式错误"}, status_code=400)

            session_factory = get_sessionmaker()
            async with session_factory() as db:
                readiness = await ai_instance_chat_test_service.validate_test_readiness(
                    db=db, instance_id=instance_id
                )

                return JSONResponse(readiness)

        except Exception as e:
            logger.error(
                "test_readiness_check_failed",
                instance_id=instance_id_str,
                error=str(e),
            )
            return JSONResponse(
                {"error": f"获取测试自检状态失败：{e!s}"},
                status_code=500,
            )

    async def archive_conversations(self, request: Request) -> JSONResponse:
        """API endpoint to archive all test conversations."""
        try:
            instance_id_str = request.path_params.get("id")
            if not instance_id_str:
                return JSONResponse({"error": "URL 中缺少实例 ID"}, status_code=400)

            try:
                instance_id = int(instance_id_str)
            except (ValueError, TypeError):
                return JSONResponse({"error": "实例 ID 格式错误"}, status_code=400)

            session_factory = get_sessionmaker()
            async with session_factory() as db:
                result = await ai_instance_chat_test_service.archive_all_test_conversations(
                    db=db, instance_id=instance_id
                )
                return JSONResponse(result)

        except AIInstanceChatTestError as e:
            logger.error("archive_conversations_failed", instance_id=instance_id_str, error=str(e))
            return JSONResponse({"success": False, "error": e.message}, status_code=400)

        except Exception as e:
            logger.error("archive_conversations_failed", instance_id=instance_id_str, error=str(e))
            return JSONResponse({"success": False, "error": f"归档失败：{e!s}"}, status_code=500)


# Create view instance
ai_instance_chat_test_view = AIInstanceChatTestView(
    label="Instance Chat Test",
    icon="",
    path="/ai_instance/chat-test/{id:int}",
    methods=["GET", "POST"],
    add_to_menu=False,  # Accessed via row actions only
)

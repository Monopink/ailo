"""
AI Instance Chat Test view for admin panel.

This module provides admin interface for testing AI instance chat functionality
following the architectural patterns and prototype design specifications.
"""

import json

from starlette.datastructures import FormData
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.core.database import get_sessionmaker
from app.services.admin.testing.instance_chat import (
    AIInstanceChatTestError,
    ai_instance_chat_test_service,
)
from app.type_defs import AIInstanceTestContext, AIInstanceTestResponse, JSONDict
from app.utils.form_helpers import FormFieldError, get_int_field, get_text_field
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Initialize templates with relative path
templates = Jinja2Templates(directory="app/admin/templates", auto_reload=True)


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

    def is_accessible(self, _request: Request) -> bool:
        """Allow access to this view."""
        return True

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the AI instance chat test interface according to prototype design."""
        action = request.query_params.get("action")

        # Route to appropriate handler based on action or method
        if action == "readiness":
            return await self.check_test_readiness(request)

        if action == "archive":
            return await self.archive_conversations(request)

        if request.method == "POST":
            return await self.handle_test_request(request)

        # Default: render the interface
        return await self._render_interface(request, templates)

    async def _render_interface(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the default GET interface for the test view."""
        try:
            instance_id = self._extract_instance_id(request)
            context = await self._build_interface_context(request, instance_id)
            return templates.TemplateResponse("custom_views/ai_instance_chat_test.html", context)
        except ValueError as exc:
            # Instance ID validation error
            return self._render_error_page(request, templates, str(exc))
        except Exception as exc:
            logger.error("ai_instance_chat_test_render_failed", error=str(exc), exc_info=True)
            return self._render_error_page(request, templates, f"加载测试页面失败: {exc!s}")

    def _extract_instance_id(self, request: Request) -> int:
        """Extract and validate instance ID from request path params."""
        instance_id_str = request.path_params.get("id")
        if not instance_id_str:
            raise ValueError("URL 中缺少实例 ID")

        try:
            return int(instance_id_str)
        except (ValueError, TypeError) as exc:
            logger.error("invalid_instance_id", instance_id=instance_id_str, error=str(exc))
            raise ValueError(f"实例 ID 无效: {instance_id_str}") from exc

    async def _build_interface_context(
        self, request: Request, instance_id: int
    ) -> AIInstanceTestContext:
        """Build context data for the interface template."""
        context: AIInstanceTestContext = {
            "request": request,
            "instance_id": instance_id,
            "page_title": "AI Instance Chat Test",
            "test_readiness": None,
            "llm_configs": [],
            "error": None,
        }

        session_factory = get_sessionmaker()
        async with session_factory() as db:
            test_readiness = await ai_instance_chat_test_service.validate_test_readiness(
                db=db, instance_id=instance_id
            )
            context["test_readiness"] = test_readiness
            if test_readiness.get("ready", False):
                context["llm_configs"] = test_readiness.get("available_llm_configs", [])

        return context

    def _render_error_page(
        self, request: Request, templates: Jinja2Templates, error_message: str
    ) -> Response:
        """Render error page with consistent format."""
        return templates.TemplateResponse(
            "custom_views/ai_instance_chat_test.html",
            {
                "request": request,
                "error": error_message,
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
            form_data = await request.form()
            instance_id = get_int_field(form_data, "instance_id")
            llm_config_name = get_text_field(form_data, "llm_config_name")
            test_message = get_text_field(form_data, "test_message")

            # Validate message - moved to separate method to avoid TRY301
            self._validate_test_message(test_message)

            response_data = await self._execute_test(
                instance_id=instance_id,
                llm_config_name=llm_config_name,
                test_message=test_message,
                form_data=form_data,
            )
            return JSONResponse(response_data)

        except FormFieldError as e:
            logger.error("ai_instance_test_form_validation_error", error=str(e))
            return JSONResponse(
                {"success": False, "error": f"字段校验失败: {e!s}"},
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
            logger.error("ai_instance_test_request_failed", error=str(e), exc_info=True)
            return JSONResponse(
                {"success": False, "error": f"测试请求异常: {e!s}"},
                status_code=500,
            )

    def _validate_test_message(self, test_message: str) -> None:
        """Validate test message is not empty."""
        if not test_message.strip():
            raise FormFieldError("测试信息不能为空")

    async def _execute_test(
        self,
        *,
        instance_id: int,
        llm_config_name: str,
        test_message: str,
        form_data: FormData,
    ) -> AIInstanceTestResponse:
        session_factory = get_sessionmaker()
        async with session_factory() as db:
            mock_overrides = self._parse_mock_overrides(form_data.get("mock_overrides_json"))
            persist_flag = self._parse_persist_flag(form_data.get("persist"))
            result = await ai_instance_chat_test_service.prepare_and_execute_test(
                db=db,
                instance_id=instance_id,
                llm_config_name=llm_config_name,
                test_message=test_message,
                mock_overrides=mock_overrides,
                persist=persist_flag,
            )
            return self._build_test_response(result, instance_id)

    def _parse_mock_overrides(self, raw_overrides: str | None) -> JSONDict | None:
        if not raw_overrides:
            return None
        try:
            parsed = json.loads(raw_overrides)
        except Exception as exc:
            raise FormFieldError("mock_overrides_json 不是合法 JSON") from exc
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _parse_persist_flag(raw_value: str | None) -> bool:
        if raw_value is None:
            return True
        val = str(raw_value).strip().lower()
        return val in ("1", "true", "on", "yes")

    def _build_test_response(self, result: JSONDict, instance_id: int) -> AIInstanceTestResponse:
        test_execution = result["test_execution"]
        latest_scores = self._sanitize_scores(
            result.get("relationship_scores_after")
        ) or self._sanitize_scores(result["validation_info"].get("relationship_scores"))
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
            "instance_profile": result["validation_info"].get("instance_profile"),
            "style": result["validation_info"].get("style"),
            "personality": result["validation_info"].get("personality"),
            "instance_settings": {
                "memory_prompt": result["validation_info"].get("memory_prompt"),
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
        return response_data

    @staticmethod
    def _sanitize_scores(scores: list[JSONDict] | None) -> list[JSONDict]:
        sanitized: list[JSONDict] = []
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
                {"error": f"获取测试自检状态失败: {e!s}"},
                status_code=500,
            )

    async def archive_conversations(self, request: Request) -> JSONResponse:
        """API endpoint to archive all test conversations."""
        instance_id_str: str | None = None
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
            return JSONResponse({"success": False, "error": f"归档失败: {e!s}"}, status_code=500)


# Create view instance
ai_instance_chat_test_view = AIInstanceChatTestView(
    label="Instance Chat Test",
    icon="",
    path="/ai_instance/chat-test/{id:int}",
    methods=["GET", "POST"],
    add_to_menu=False,  # Accessed via row actions only
)

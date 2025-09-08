"""
Custom views for non-database functionality.
"""

from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import SessionLocal
from models.user import User, UserSession
from models.ai.character import AICharacter
from models.message.message import MessageHistory
from models.admin import AdminUser
from utils.logging import get_logger

logger = get_logger(__name__)


class DashboardView(CustomView):
    """Dashboard with system overview."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render dashboard with system statistics."""

        async with SessionLocal() as db:
            try:
                # Get real statistics from database
                stats = await self._get_dashboard_stats(db)

                context = {
                    "request": request,
                    "stats": stats
                }

                return templates.TemplateResponse("custom_views/dashboard.html", context)

            except Exception as e:
                logger.error("dashboard_stats_error", error=str(e), exc_info=True)
                # Fallback to default stats on error
                context = {
                    "request": request,
                    "stats": {
                        "total_users": 0,
                        "total_ai_characters": 0,
                        "total_messages": 0,
                        "active_sessions": 0,
                    }
                }
                return templates.TemplateResponse("custom_views/dashboard.html", context)

    async def _get_dashboard_stats(self, db: AsyncSession) -> dict:
        """Get dashboard statistics from database."""

        # Count total users
        total_users_result = await db.execute(select(func.count(User.id)))
        total_users = total_users_result.scalar() or 0

        # Count total AI characters
        total_ai_characters_result = await db.execute(select(func.count(AICharacter.id)))
        total_ai_characters = total_ai_characters_result.scalar() or 0

        # Count total messages
        total_messages_result = await db.execute(select(func.count(MessageHistory.id)))
        total_messages = total_messages_result.scalar() or 0

        # Count active sessions (sessions that are active)
        active_sessions_result = await db.execute(
            select(func.count(UserSession.id)).where(UserSession.is_active == True)
        )
        active_sessions = active_sessions_result.scalar() or 0

        return {
            "total_users": total_users,
            "total_ai_characters": total_ai_characters,
            "total_messages": total_messages,
            "active_sessions": active_sessions,
        }


class AICharacterChatTestView(CustomView):
    """AI Character chat test view - integrated with character management."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render AI character chat test interface."""

        # Get character IDs from query parameters
        character_ids = request.query_params.get("character_ids", "").split(",")
        character_ids = [cid.strip() for cid in character_ids if cid.strip()]

        context = {
            "request": request,
            "character_ids": character_ids,
            "response": None,
            "error": None,
        }

        if request.method == "POST":
            try:
                form = await request.form()
                user_message = form.get("message", "")
                character_id = form.get("character_id", "")

                if not user_message:
                    context["error"] = "请输入消息内容"
                elif not character_id:
                    context["error"] = "请选择AI角色"
                else:
                    # TODO: Implement AI chat simulation with specific character
                    async with SessionLocal() as db:
                        # Get character info for better simulation
                        character_result = await db.execute(
                            select(AICharacter).where(AICharacter.id == int(character_id))
                        )
                        character = character_result.scalar_one_or_none()

                        if character:
                            context["response"] = {
                                "user_message": user_message,
                                "ai_response": f"[模拟回复 - 角色ID: {character.qiao_id}] 收到消息: {user_message}",
                                "character_id": character_id,
                                "character_qiao_id": character.qiao_id,
                            }
                        else:
                            context["error"] = "找不到指定的AI角色"

                    logger.info("ai_character_chat_test_executed",
                              message=user_message, character_id=character_id)

            except Exception as e:
                logger.error("ai_character_chat_test_error", error=str(e), exc_info=True)
                context["error"] = f"测试失败: {str(e)}"

        return templates.TemplateResponse("custom_views/ai_character_chat_test.html", context)


class SendMessageView(CustomView):
    """LeanCloud message sending tool."""
    
    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render message sending interface."""
        
        context = {
            "request": request,
            "result": None,
            "error": None,
        }
        
        if request.method == "POST":
            try:
                form = await request.form()
                to_user = form.get("to_user", "")
                message = form.get("message", "")
                message_type = form.get("message_type", "text")
                
                if not to_user or not message:
                    context["error"] = "请填写接收用户和消息内容"
                else:
                    # TODO: Implement LeanCloud message sending
                    context["result"] = {
                        "to_user": to_user,
                        "message": message,
                        "message_type": message_type,
                        "status": "success",
                        "message_id": "mock_message_id_123",
                    }
                    
                    logger.info("send_message_executed", to_user=to_user, message_type=message_type)
                    
            except Exception as e:
                logger.error("send_message_error", error=str(e), exc_info=True)
                context["error"] = f"发送失败: {str(e)}"
        
        return templates.TemplateResponse("custom_views/send_message.html", context)


class LLMTestView(CustomView):
    """LLM model testing tool."""
    
    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render LLM testing interface."""
        
        context = {
            "request": request,
            "result": None,
            "error": None,
            "available_models": [
                {"id": "doubao-pro-4k", "name": "豆包 Pro 4K"},
                {"id": "doubao-pro-32k", "name": "豆包 Pro 32K"},
                {"id": "doubao-pro-128k", "name": "豆包 Pro 128K"},
            ]
        }
        
        if request.method == "POST":
            try:
                form = await request.form()
                prompt = form.get("prompt", "")
                model = form.get("model", "doubao-pro-4k")
                temperature = float(form.get("temperature", "0.7"))
                max_tokens = int(form.get("max_tokens", "1000"))
                
                if not prompt:
                    context["error"] = "请输入测试提示词"
                else:
                    # TODO: Implement LLM testing
                    context["result"] = {
                        "prompt": prompt,
                        "model": model,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "response": f"[模拟回复] 使用模型 {model} 处理提示词: {prompt[:50]}...",
                        "tokens_used": 150,
                        "response_time": "1.2s",
                    }
                    
                    logger.info("llm_test_executed", model=model, prompt_length=len(prompt))
                    
            except Exception as e:
                logger.error("llm_test_error", error=str(e), exc_info=True)
                context["error"] = f"测试失败: {str(e)}"
        
        return templates.TemplateResponse("custom_views/llm_test.html", context)

"""
Custom views for non-database functionality.
All business logic is handled through internal API calls.
"""

import httpx
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from utils.logging import get_logger

logger = get_logger(__name__)


class DashboardView(CustomView):
    """Dashboard with system overview."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render dashboard with system statistics."""

        try:
            # Call internal dashboard API
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/admin-api/dashboard/stats")

                if response.status_code == 200:
                    api_result = response.json()
                    if api_result.get("success"):
                        stats = api_result.get("data", {})
                    else:
                        logger.error("dashboard_api_error", error=api_result.get("error"))
                        stats = self._get_fallback_stats()
                else:
                    logger.error("dashboard_api_http_error", status_code=response.status_code)
                    stats = self._get_fallback_stats()

            context = {"request": request, "stats": stats}
            return templates.TemplateResponse("custom_views/dashboard.html", context)

        except Exception as e:
            logger.error("dashboard_render_error", error=str(e), exc_info=True)
            context = {
                "request": request,
                "stats": self._get_fallback_stats(),
            }
            return templates.TemplateResponse("custom_views/dashboard.html", context)

    def _get_fallback_stats(self) -> dict:
        """Get fallback statistics when API call fails."""
        return {
            "total_users": 0,
            "total_ai_characters": 0,
            "total_messages": 0,
            "active_sessions": 0,
            "today_new_users": 0,
            "today_messages": 0,
            "system_status": "unknown",
        }


class SystemSettingsView(CustomView):
    """System settings management interface."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render system settings interface."""

        context = {
            "request": request,
            "success": None,
            "error": None,
            "config_groups": {
                "system": [
                    {"key": "debug_mode", "value": "false", "description": "Debug mode"},
                    {"key": "log_level", "value": "INFO", "description": "Log level"},
                ],
                "llm": [
                    {"key": "default_temperature", "value": "0.7", "description": "Default temperature"},
                    {"key": "max_tokens", "value": "1000", "description": "Max tokens"},
                ],
            },
        }

        if request.method == "POST":
            try:
                await request.form()  # Get form data
                # TODO: Call system settings API
                context["success"] = "Settings updated successfully (placeholder)"
                logger.info("system_settings_updated")

            except Exception as e:
                logger.error("system_settings_error", error=str(e), exc_info=True)
                context["error"] = f"Failed to update settings: {str(e)}"

        return templates.TemplateResponse("custom_views/system_settings.html", context)

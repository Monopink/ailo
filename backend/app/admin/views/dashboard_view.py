"""
Dashboard views for non-database functionality.
All business logic is handled through internal API calls.
"""

from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from utils.logging import get_logger

logger = get_logger(__name__)


class DashboardView(CustomView):
    """Dashboard with system overview."""

    def is_active(self, request: Request) -> bool:
        """Check if current page is dashboard by comparing full path including base_url."""
        # Dashboard is the index page, so check if path ends with base_url or base_url + "/"
        path = request.scope["path"]
        # Get base_url from admin instance (e.g., "/qiao-dash")
        try:
            base_url = request.app.state.ADMIN.base_url
            return path == base_url or path == base_url + "/"
        except AttributeError:
            # Fallback if base_url is not available
            return path.endswith(self.path)

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render dashboard page with initial data from database."""
        try:
            # Get database session
            db = request.state.session

            from crud.system import system_configs
            from services.config import config_service
            from services.message.health import get_message_service_status

            # Read initial data from database
            webhook_token = await system_configs.get_config_value(db, config_key="leancloud_webhook_token")
            api_base_url = await system_configs.get_config_value(db, config_key="api_base_url")
            conversation_id = await system_configs.get_config_value(
                db, config_key="leancloud_service_conversation_id"
            )

            # Get LeanCloud config
            leancloud_config = await config_service.get_leancloud_config(db)

            # Check message service health
            health_status = await get_message_service_status(db)

            # Construct webhook URL
            webhook_url = None
            if webhook_token and api_base_url:
                webhook_url = f"{api_base_url}/api/v1/webhook/leancloud/{webhook_token}"

            context = {
                "request": request,
                "webhook_url": webhook_url,
                "webhook_token": webhook_token,
                "token_length": len(webhook_token) if webhook_token else 0,
                "conversation_id": conversation_id,
                "leancloud_config": {
                    "configured": bool(
                        leancloud_config.get("app_id")
                        and leancloud_config.get("master_key")
                        and leancloud_config.get("base_url")
                    ),
                    "has_app_id": bool(leancloud_config.get("app_id")),
                    "has_master_key": bool(leancloud_config.get("master_key")),
                    "has_base_url": bool(leancloud_config.get("base_url")),
                },
                "message_service_health": health_status,
            }
            return templates.TemplateResponse("custom_views/dashboard.html", context)
        except Exception as e:
            logger.error("dashboard_render_error", error=str(e), exc_info=True)
            context = {"request": request}
            return templates.TemplateResponse("custom_views/dashboard.html", context)

"""Dashboard views for non-database functionality.
All business logic is handled through internal API calls.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.core.config import get_settings
from app.crud.system import system_configs
from app.enums import ContactRequestStatus
from app.exceptions import MissingConfigurationError
from app.models.contact import ContactRequest
from app.services.config import config_service
from app.services.media.config import get_media_base_url, get_media_base_url_source
from app.services.message.monitoring.health import get_message_service_status
from app.services.message.providers.leancloud.url_builder import (
    build_leancloud_webhook_url,
)
from app.utils.logging import get_logger

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

            # Read initial data from database
            webhook_token = await system_configs.get_config_value(
                db, config_key="leancloud_im_webhook_token"
            )
            api_base_url = await system_configs.get_config_value(db, config_key="api_base_url")
            conversation_id = await system_configs.get_config_value(
                db, config_key="leancloud_im_service_conversation_id"
            )

            # Get LeanCloud config
            leancloud_config = await config_service.get_leancloud_config(db)

            # Check message service health
            health_status = await get_message_service_status(db)

            # Get pending contact requests statistics
            window_start = datetime.now(UTC) - timedelta(hours=24)
            pending_total_stmt = select(func.count(ContactRequest.id)).where(
                ContactRequest.status == ContactRequestStatus.PENDING,
                ContactRequest.failure_code.is_not(None),
            )
            success_stmt = select(func.count(ContactRequest.id)).where(
                ContactRequest.status == ContactRequestStatus.ACCEPTED,
                ContactRequest.last_retry_at.is_not(None),
                ContactRequest.last_retry_at >= window_start,
            )
            failure_stmt = select(func.count(ContactRequest.id)).where(
                ContactRequest.status == ContactRequestStatus.PENDING,
                ContactRequest.failure_code.is_not(None),
                ContactRequest.last_retry_at.is_not(None),
                ContactRequest.last_retry_at >= window_start,
            )

            pending_total = (await db.execute(pending_total_stmt)).scalar_one() or 0
            last24h_success = (await db.execute(success_stmt)).scalar_one() or 0
            last24h_failed = (await db.execute(failure_stmt)).scalar_one() or 0

            # Construct webhook URL
            webhook_url = None
            if webhook_token and api_base_url:
                webhook_url = build_leancloud_webhook_url(
                    api_base_url=str(api_base_url),
                    webhook_token=str(webhook_token),
                )

            media_db_value = await system_configs.get_config_value(
                db, config_key="media_public_base_url"
            )
            settings = get_settings()
            runtime_source = get_media_base_url_source()
            try:
                runtime_cdn = get_media_base_url()
            except MissingConfigurationError:
                runtime_cdn = ""

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
                "pending_contact_requests": {
                    "pending_total": pending_total,
                    "last24h_success": last24h_success,
                    "last24h_failed": last24h_failed,
                },
                "media_cdn_status": {
                    "db_value": media_db_value or "",
                    "env_value": settings.MEDIA_PUBLIC_BASE_URL or "",
                    "runtime_value": runtime_cdn,
                    "runtime_source": runtime_source,
                },
            }
            return templates.TemplateResponse("custom_views/dashboard.html", context)
        except Exception as e:
            logger.error("dashboard_render_error", error=str(e), exc_info=True)
            context = {
                "request": request,
                "media_cdn_status": {
                    "db_value": "",
                    "env_value": "",
                    "runtime_value": "",
                    "runtime_source": "unavailable",
                },
            }
            return templates.TemplateResponse("custom_views/dashboard.html", context)

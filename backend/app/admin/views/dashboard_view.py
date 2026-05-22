"""Dashboard views for non-database functionality.
All business logic is handled through internal API calls.
"""

from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.services.contact.incomplete_admin_service import get_incomplete_contact_request_overview
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
            db = request.state.session
            overview = await get_incomplete_contact_request_overview(db)

            context = {
                "request": request,
                "incomplete_contact_requests": {
                    "incomplete_total": overview.get("incomplete_total", 0),
                    "last24h_success": overview.get("last24h_success_requests", 0),
                    "last24h_failed": overview.get("last24h_failed_requests", 0),
                },
            }
            return templates.TemplateResponse("custom_views/dashboard.html", context)
        except Exception as e:
            logger.error("dashboard_render_error", error=str(e), exc_info=True)
            context = {
                "request": request,
            }
            return templates.TemplateResponse("custom_views/dashboard.html", context)

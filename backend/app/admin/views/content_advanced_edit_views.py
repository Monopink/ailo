"""Custom views for advanced editing of content entities."""

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.core.database import get_sessionmaker
from app.enums import AppPageCategory, AppPageSourceType, AppPageStatus
from app.models.content import AppPage


async def _load_app_page(page_id: int) -> AppPage:
    session_factory = get_sessionmaker()
    async with session_factory() as db:
        page = await db.get(AppPage, page_id)
        if page is None:
            raise HTTPException(status_code=404, detail="App page not found")
        return page


def _enum_label(
    value: int,
    enum_type: type[AppPageCategory] | type[AppPageSourceType] | type[AppPageStatus],
) -> str:
    """Render a stable English display label for known enum values."""
    try:
        enum_value = enum_type(value)
    except ValueError:
        return "Unknown"
    return enum_value.name.replace("_", " ").title()


class AppPageAdvancedEditView(CustomView):
    """Advanced page for app page editing and rendering."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render app page advanced editor."""
        try:
            page_id = int(request.path_params["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid app page ID") from exc

        page = await _load_app_page(page_id)
        context = {
            "request": request,
            "document": page,
            "page_info": {
                "page_category_text": _enum_label(page.page_category, AppPageCategory),
                "source_type_text": _enum_label(page.source_type, AppPageSourceType),
                "status_text": _enum_label(page.status, AppPageStatus),
            },
        }
        return templates.TemplateResponse("custom_views/app_page_advanced_edit.html", context)


class AppPagePreviewView(CustomView):
    """Read-only preview page for rendered app page HTML."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render raw HTML content for client-like preview."""
        try:
            page_id = int(request.path_params["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid app page ID") from exc

        page = await _load_app_page(page_id)
        return HTMLResponse(content=str(page.content_html or ""))


app_page_advanced_edit_view = AppPageAdvancedEditView(
    label="Advanced Edit",
    name="app_page_advanced_edit",
    path="/app_page/advanced-edit/{id:int}",
    add_to_menu=False,
)

app_page_preview_view = AppPagePreviewView(
    label="Preview",
    name="app_page_preview",
    path="/app_page/preview/{id:int}",
    add_to_menu=False,
)

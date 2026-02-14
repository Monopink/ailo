"""Admin internal chat console for realtime chat.

This view is gated by Starlette-Admin session (page access only).
All business APIs and WebSocket use JWT (see docs/spec/admin/chat-console.md).
"""

from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

templates = Jinja2Templates(directory="app/admin/templates", auto_reload=True)


class ChatConsoleView(CustomView):
    """Internal chat console page."""

    def is_accessible(self, _request: Request) -> bool:
        return True

    def is_active(self, request: Request) -> bool:
        """Mark current sidebar menu item active.

        Starlette-Admin mounts under a base_url (e.g. "/qiao-dash"); CustomView.path is
        relative to that. Compare against the full request path for consistent behavior.
        """

        path = request.scope["path"]
        try:
            base_url = request.app.state.ADMIN.base_url
            full_path = base_url + self.path
            return path == full_path
        except AttributeError:
            return path.endswith(self.path)

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        return templates.TemplateResponse(
            "custom_views/chat_console.html",
            {"request": request, "page_title": "Chat Console"},
        )


chat_console_view = ChatConsoleView(
    label="Chat Console",
    icon="fa fa-terminal",
    path="/chat-console",
    methods=["GET"],
    add_to_menu=True,
)

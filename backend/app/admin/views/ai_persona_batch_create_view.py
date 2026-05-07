"""Custom view for admin persona batch creation."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView


class AIPersonaBatchCreateView(CustomView):
    """Render persona batch create page."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        return templates.TemplateResponse(
            "custom_views/ai_persona_batch_create.html", {"request": request}
        )


ai_persona_batch_create_view = AIPersonaBatchCreateView(
    label="Persona Batch Create",
    icon="fa fa-layer-group",
    name="ai_persona_batch_create",
    path="/ai_persona/batch-create",
    add_to_menu=False,
)

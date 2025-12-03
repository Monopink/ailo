"""
AI Score Algorithm Test view for admin panel.

This module provides admin interface for testing AI score algorithms
and relationship selection logic.
"""

from typing import Any

from sqlalchemy import text
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.core.database import get_sessionmaker
from app.services.admin.data.style_dimensions import get_dimension_relationship_mappings
from app.services.admin.testing.style_algorithm import run_style_score_test
from app.services.ai.utils.position_mapping import get_algorithm_info, get_algorithm_param_specs
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Initialize templates with relative path
templates = Jinja2Templates(directory="admin/templates", auto_reload=True)


class AIStyleTestView(CustomView):
    """AI Score Algorithm Test interface."""

    def is_accessible(self, _request: Request) -> bool:
        """Allow access to this view."""
        return True

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the AI score algorithm test interface."""
        try:
            # Get style_id from path parameters
            style_id_raw = request.path_params.get("id")

            # Convert to int if present
            try:
                style_id = int(style_id_raw)
            except (ValueError, TypeError) as e:
                logger.error(
                    "invalid_style_id_format",
                    style_id_raw=style_id_raw,
                    error=str(e),
                )
                return templates.TemplateResponse(
                    "custom_views/ai_style_test.html",
                    {
                        "request": request,
                        "algorithm_info": {
                            1: get_algorithm_info(1),
                            2: get_algorithm_info(2),
                        },
                        "algorithm_param_specs": get_algorithm_param_specs(),
                        "error": f"Invalid style_id: {style_id_raw}",
                        "selected_style_id": None,
                        "relationships": [],
                        "dimensions": [],
                        "dimension_relationship_mappings": [],
                    },
                    status_code=400,
                )

            # Debug logging
            logger.info(
                "score_algorithm_test_render",
                style_id_raw=style_id_raw,
                style_id=style_id,
                path=request.url.path,
                path_params=dict(request.path_params),
            )

            context = {
                "request": request,
                "algorithm_info": {},
                "algorithm_param_specs": get_algorithm_param_specs(),
                "test_result": None,
                "error": None,
                "selected_style_id": style_id,
                "style_info": None,
                "relationships": [],
                "dimensions": [],
                "dimension_relationship_mappings": [],
            }

            # Get algorithm information from services layer
            context["algorithm_info"] = {
                1: get_algorithm_info(1),
                2: get_algorithm_info(2),
            }

            # Get database session
            session_factory = get_sessionmaker()
            async with session_factory() as db:
                # Get dimensions and relationships for the selected style (style_id is enforced)
                try:
                    # Fetch style basic info
                    style_info_result = await db.execute(
                        text(
                            """
                            SELECT id, display_name, status
                            FROM ai_styles
                            WHERE id = :style_id
                            """
                        ),
                        {"style_id": int(style_id)},
                    )
                    srow = style_info_result.fetchone()
                    if srow:
                        context["style_info"] = {
                            "id": srow.id,
                            "display_name": getattr(srow, "display_name", None),
                            "status": getattr(srow, "status", None),
                        }

                    dimensions_result = await db.execute(
                        text(
                            """
                            SELECT d.name, d.display_name, asd.initial_position
                            FROM ai_style_dimensions AS asd
                            JOIN ai_dimensions AS d ON d.id = asd.dimension_id
                            WHERE asd.style_id = :style_id
                            ORDER BY d.name
                            """
                        ),
                        {"style_id": int(style_id)},
                    )
                    dimensions_rows = dimensions_result.fetchall()

                    logger.info(
                        "dimensions_query_result",
                        style_id=style_id,
                        count=len(dimensions_rows),
                        dimensions=[
                            {"name": r.name, "display_name": r.display_name}
                            for r in dimensions_rows
                        ],
                    )

                    context["dimensions"] = [
                        {
                            "name": row.name,
                            "display_name": row.display_name,
                            "initial_position": row.initial_position,
                        }
                        for row in dimensions_rows
                    ]

                    # Get relationships for the selected style
                    relationships_result = await db.execute(
                        text(
                            """
                            SELECT DISTINCT r.id, r.display_name
                            FROM ai_relationships r
                            JOIN ai_dimension_relationship_mappings drm ON r.id = drm.relationship_id
                            JOIN ai_style_dimensions asd ON asd.dimension_id = drm.dimension_id
                            WHERE asd.style_id = :style_id
                            ORDER BY r.display_name
                        """
                        ),
                        {"style_id": int(style_id)},
                    )
                    context["relationships"] = [
                        {
                            "id": row.id,
                            "display_name": row.display_name,
                        }
                        for row in relationships_result.fetchall()
                    ]

                    # Fetch dimension relationship mappings for visualization
                    mappings = await get_dimension_relationship_mappings(
                        db, style_id=int(style_id), limit=100
                    )
                    context["dimension_relationship_mappings"] = mappings

                except (ValueError, TypeError) as e:
                    logger.error("invalid_style_id", style_id=style_id, error=str(e))
                    context["dimensions"] = []
                    context["relationships"] = []
                    context["error"] = f"Invalid style_id: {style_id}"

                # Handle POST requests
                if request.method == "POST":
                    form_data = await request.form()
                    action = form_data.get("action")

                    if action == "test_algorithm":
                        context["test_result"] = await self._handle_test_algorithm(
                            form_data, style_id
                        )
                        # Preserve form data for re-rendering
                        context["form_data"] = dict(form_data)

            return templates.TemplateResponse("custom_views/ai_style_test.html", context)

        except Exception as e:
            logger.error("ai_style_test_render_failed", error=str(e), exc_info=True)
            return templates.TemplateResponse(
                "custom_views/ai_style_test.html",
                {
                    "request": request,
                    "algorithm_info": {
                        1: get_algorithm_info(1),
                        2: get_algorithm_info(2),
                    },
                    "error": f"Failed to render score test interface: {e!s}",
                    "dimension_relationship_mappings": [],
                },
            )

    async def _handle_test_algorithm(self, form_data, style_id: int) -> dict[str, Any]:
        """Handle score algorithm testing via admin service layer."""
        try:
            session_factory = get_sessionmaker()
            async with session_factory() as db:
                fd = dict(form_data)
                result = await run_style_score_test(db, style_id=int(style_id), form_data=fd)
                result["algorithm_info"] = {1: get_algorithm_info(1), 2: get_algorithm_info(2)}
                return result
        except Exception as e:
            logger.error("ai_style_test_failed", error=str(e))
            return {"success": False, "message": f"Algorithm test failed: {e!s}"}


# Create view instance
ai_style_test_view = AIStyleTestView(
    label="Style Test",
    icon="",
    path="/ai_style/test/{id:int}",
    methods=["GET", "POST"],
    add_to_menu=False,  # Accessed via row actions only
)

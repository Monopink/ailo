"""AI Score Algorithm Test view for admin panel.

This module provides admin interface for testing AI score algorithms
and relationship selection logic.
"""

from sqlalchemy import text
from starlette.datastructures import FormData
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.core.database import get_sessionmaker
from app.services.admin.data.style_dimensions import get_dimension_relationship_mappings
from app.services.admin.testing.style_algorithm import run_style_score_test
from app.services.ai.utils.position_mapping import get_algorithm_info, get_algorithm_param_specs
from app.type_defs import JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Initialize templates with relative path
templates = Jinja2Templates(directory="app/admin/templates", auto_reload=True)

_V1_PARAM_I18N: dict[str, tuple[str, str]] = {
    "left_sensitivity": ("左侧敏感度（%）", "初始位置左侧区间敏感度（-100 到 100）。"),
    "right_sensitivity": ("右侧敏感度（%）", "初始位置右侧区间敏感度（-100 到 100）。"),
    "left_positive_gain": ("左侧正向增益", "左侧敏感度 ≥ 0 时使用的对数增益。"),
    "left_negative_gain": ("左侧负向增益", "左侧敏感度 < 0 时使用的对数增益。"),
    "right_positive_gain": ("右侧正向增益", "右侧敏感度 ≥ 0 时使用的对数增益。"),
    "right_negative_gain": ("右侧负向增益", "右侧敏感度 < 0 时使用的对数增益。"),
}
_ALGORITHM_NONE = 1
_ALGORITHM_V1 = 2


def _localize_algorithm_info() -> dict[int, JSONDict]:
    """Build localized algorithm metadata for style-test page."""
    algorithm_info: dict[int, JSONDict] = {
        _ALGORITHM_NONE: get_algorithm_info(_ALGORITHM_NONE),
        _ALGORITHM_V1: get_algorithm_info(_ALGORITHM_V1),
    }

    if _ALGORITHM_NONE in algorithm_info:
        algorithm_info[_ALGORITHM_NONE]["name"] = "无偏移（直接映射）"
    if _ALGORITHM_V1 in algorithm_info:
        algorithm_info[_ALGORITHM_V1]["name"] = "V1（非线性映射）"
    return algorithm_info


def _localize_algorithm_param_specs() -> dict[int, list[JSONDict]]:
    """Build localized algorithm parameter specs for style-test page."""
    raw_specs = get_algorithm_param_specs()
    localized: dict[int, list[JSONDict]] = {}
    for algorithm_id, specs in raw_specs.items():
        localized_specs: list[JSONDict] = []
        for spec in specs:
            spec_name = spec["name"]
            localized_spec: JSONDict = dict(spec)
            if spec_name in _V1_PARAM_I18N:
                label, description = _V1_PARAM_I18N[spec_name]
                localized_spec["label"] = label
                localized_spec["description"] = description
            localized_specs.append(localized_spec)
        localized[int(algorithm_id)] = localized_specs
    return localized


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
                        "algorithm_info": _localize_algorithm_info(),
                        "algorithm_param_specs": _localize_algorithm_param_specs(),
                        "error": f"无效的 style_id: {style_id_raw}",
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
                "algorithm_param_specs": _localize_algorithm_param_specs(),
                "test_result": None,
                "error": None,
                "selected_style_id": style_id,
                "style_info": None,
                "relationships": [],
                "dimensions": [],
                "dimension_relationship_mappings": [],
            }

            # Get algorithm information from services layer
            context["algorithm_info"] = _localize_algorithm_info()

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
                            JOIN ai_dimension_relationship_mappings drm
                                ON r.id = drm.relationship_id
                            JOIN ai_style_dimensions asd
                                ON asd.dimension_id = drm.dimension_id
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
                    context["error"] = f"无效的 style_id: {style_id}"

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
                    "algorithm_info": _localize_algorithm_info(),
                    "error": f"渲染分数测试页面失败: {e!s}",
                    "dimension_relationship_mappings": [],
                },
            )

    async def _handle_test_algorithm(self, form_data: FormData, style_id: int) -> JSONDict:
        """Handle score algorithm testing via admin service layer."""
        try:
            session_factory = get_sessionmaker()
            async with session_factory() as db:
                fd = dict(form_data)
                result = await run_style_score_test(db, style_id=int(style_id), form_data=fd)
                result["algorithm_info"] = _localize_algorithm_info()
                return result
        except Exception as e:
            logger.error("ai_style_test_failed", error=str(e))
            return {"success": False, "message": f"算法测试失败: {e!s}"}


# Create view instance
ai_style_test_view = AIStyleTestView(
    label="风格测试",
    icon="",
    path="/ai_style/test/{id:int}",
    methods=["GET", "POST"],
    add_to_menu=False,  # Accessed via row actions only
)

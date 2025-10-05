"""
AI character testing views for admin panel.

This module provides admin interface for testing AI characters following
the architectural patterns and prototype design specifications.
"""

from typing import Dict, Any, List, Optional
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView
from sqlalchemy import text

from core.database import SessionLocal
from services.admin.ai_character_chat import ai_character_chat_test_service, AICharacterChatTestError
from services.ai.utils.score_algorithm import (
    apply_score_algorithm,
    get_algorithm_info,
    validate_algorithm_params,
)
from utils.logging import get_logger
from utils.form_helpers import get_text_field, get_int_field, FormFieldError

logger = get_logger(__name__)

# Initialize templates with relative path
templates = Jinja2Templates(directory="admin/templates", auto_reload=True)


class AICharacterChatTestView(CustomView):
    """
    AI Character Chat Test interface following prototype design.

    Prototype Requirements:
    - Only includes: LLM Configuration dropdown + Test message input
    - No AI character selection (fixed via URL parameter)
    - No user selection (automatically matched)
    - Shows prerequisite validation status
    - Supports continuous testing with context preservation
    """

    def is_accessible(self, request: Request) -> bool:
        """Allow access to this view."""
        return True

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the AI character chat test interface according to prototype design."""

        # Check action parameter for API endpoints
        action = request.query_params.get("action")

        if action == "readiness":
            return await self.check_test_readiness(request)

        # Handle POST requests (test execution)
        if request.method == "POST":
            return await self.handle_test_request(request)

        # Default GET request - render the interface
        try:
            # Get character_id from path parameters (required)
            character_id_str = request.path_params.get("id")
            if not character_id_str:
                return templates.TemplateResponse(
                    "custom_views/ai_character_chat_test.html",
                    {
                        "request": request,
                        "error": "Character ID is required in URL path",
                        "page_title": "AI Character Chat Test - Error",
                    },
                )

            try:
                character_id = int(character_id_str)
            except (ValueError, TypeError) as e:
                logger.error("invalid_character_id", character_id=character_id_str, error=str(e))
                return templates.TemplateResponse(
                    "custom_views/ai_character_chat_test.html",
                    {
                        "request": request,
                        "error": f"Invalid character_id: {character_id_str}",
                        "page_title": "AI Character Chat Test - Error",
                    },
                )

            # Initialize context
            context = {
                "request": request,
                "character_id": character_id,
                "page_title": "AI Character Chat Test",
                "test_readiness": None,
                "llm_configs": [],
                "error": None,
            }

            async with SessionLocal() as db:
                # Check test readiness using the new service
                test_readiness = await ai_character_chat_test_service.validate_test_readiness(
                    db=db, character_id=character_id
                )
                context["test_readiness"] = test_readiness

                # Get available LLM configurations
                if test_readiness.get("ready", False):
                    context["llm_configs"] = test_readiness.get("available_llm_configs", [])

            return templates.TemplateResponse("custom_views/ai_character_chat_test.html", context)

        except Exception as e:
            logger.error("ai_character_chat_test_render_failed", error=str(e), exc_info=True)
            return templates.TemplateResponse(
                "custom_views/ai_character_chat_test.html",
                {
                    "request": request,
                    "error": f"Failed to load AI character chat test interface: {str(e)}",
                    "page_title": "AI Character Chat Test - Error",
                },
            )

    async def handle_test_request(self, request: Request) -> JSONResponse:
        """
        Handle AI character test request using the new unified service.

        This method leverages the facade service to execute the complete test flow:
        validation -> user matching -> execution (calling main logic).
        """
        try:
            # Parse request data with type-safe extraction
            form_data = await request.form()

            try:
                character_id = get_int_field(form_data, "character_id")
                llm_config_key = get_text_field(form_data, "llm_config_key")
                test_message = get_text_field(form_data, "test_message")
            except FormFieldError as e:
                return JSONResponse(
                    {"error": str(e)},
                    status_code=400,
                )

            # Validate message content
            if not test_message.strip():
                return JSONResponse(
                    {"error": "Test message cannot be empty"},
                    status_code=400,
                )

            async with SessionLocal() as db:
                # Use the unified facade service for complete test execution
                result = await ai_character_chat_test_service.prepare_and_execute_test(
                    db=db,
                    character_id=character_id,
                    llm_config_key=llm_config_key,
                    test_message=test_message,
                )

                # Format response for frontend display
                test_execution = result["test_execution"]

                response_data = {
                    "success": True,
                    "test_mode": test_execution["test_mode"],
                    "log_id": test_execution["log_id"],
                    "character_info": {
                        "qiao_id": result["validation_info"]["character"]["qiao_id"],
                        "category": result["validation_info"]["character"]["category"],
                        "style": result["validation_info"]["style"]["display_name"],
                        "personality": result["validation_info"]["personality"]["display_name"],
                    },
                    "test_user_info": {
                        "qiao_id": result["test_user_info"]["test_user"]["qiao_id"],
                        "username": result["test_user_info"]["test_user"]["username"],
                        "nickname": result["test_user_info"]["test_user_profile"]["nickname"],
                    },
                    "conversation": test_execution["conversation"],
                    "performance": test_execution["performance"],
                    "relationship_scores": result["validation_info"]["relationship_scores"],
                    "request_payload": test_execution.get("request_payload"),
                }

                logger.info(
                    "ai_character_test_completed_successfully",
                    character_id=character_id,
                    response_time_ms=test_execution["performance"]["response_time_ms"],
                    messages_count=len(test_execution["conversation"]["all_messages"]),
                )

                return JSONResponse(response_data)

        except FormFieldError as e:
            logger.error(
                "ai_character_test_form_validation_error",
                error=str(e),
            )
            return JSONResponse(
                {"success": False, "error": str(e)},
                status_code=400,
            )

        except AICharacterChatTestError as e:
            logger.error(
                "ai_character_test_service_error",
                error_code=e.error_code,
                error=str(e),
            )
            return JSONResponse(
                {
                    "success": False,
                    "error": e.message,
                    "error_code": e.error_code,
                    "suggestions": e.suggestions,
                },
                status_code=400,
            )

        except Exception as e:
            logger.error(
                "ai_character_test_request_failed",
                error=str(e),
                exc_info=True,
            )
            return JSONResponse(
                {"success": False, "error": f"Test request failed: {str(e)}"},
                status_code=500,
            )

    async def check_test_readiness(self, request: Request) -> JSONResponse:
        """API endpoint to check test readiness status."""
        try:
            character_id_str = request.path_params.get("id")
            if not character_id_str:
                return JSONResponse(
                    {"error": "Missing character_id in URL path"},
                    status_code=400,
                )

            try:
                character_id = int(character_id_str)
            except (ValueError, TypeError):
                return JSONResponse(
                    {"error": "Invalid character_id format"},
                    status_code=400,
                )

            async with SessionLocal() as db:
                readiness = await ai_character_chat_test_service.validate_test_readiness(
                    db=db, character_id=character_id
                )

                return JSONResponse(readiness)

        except Exception as e:
            logger.error(
                "test_readiness_check_failed",
                character_id=character_id_str,
                error=str(e),
            )
            return JSONResponse(
                {"error": f"Failed to check test readiness: {str(e)}"},
                status_code=500,
            )


class AIScoreAlgorithmTestView(CustomView):
    """AI Score Algorithm Test interface - Kept largely unchanged for reference."""

    def is_accessible(self, _request: Request) -> bool:
        """Allow access to this view."""
        return True

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the AI score algorithm test interface."""
        try:
            # Get style_id from path parameters
            style_id_raw = request.path_params.get("id")

            # Convert to int if present
            style_id = None
            if style_id_raw:
                try:
                    style_id = int(style_id_raw)
                except (ValueError, TypeError) as e:
                    logger.error(
                        "invalid_style_id_format",
                        style_id_raw=style_id_raw,
                        error=str(e),
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
                "test_result": None,
                "error": None,
                "selected_style_id": style_id,
                "relationships": [],
                "dimensions": [],
            }

            # Get algorithm information from services layer
            context["algorithm_info"] = {
                1: get_algorithm_info(1),
                2: get_algorithm_info(2),
            }

            # Get database session
            async with SessionLocal() as db:
                # Get dimensions and relationships for the selected style
                if style_id:
                    try:
                        dimensions_result = await db.execute(
                            text(
                                """
                                SELECT name, display_name, initial_position
                                FROM ai_relationship_dimensions
                                WHERE style_id = :style_id
                                ORDER BY name
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
                                {"name": r.name, "display_name": r.display_name} for r in dimensions_rows
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
                                SELECT DISTINCT r.id, r.name, r.display_name
                                FROM ai_relationships r
                                JOIN ai_relationship_indexes ri ON r.id = ri.relationship_id
                                WHERE ri.style_id = :style_id
                                ORDER BY r.display_name
                            """
                            ),
                            {"style_id": int(style_id)},
                        )
                        context["relationships"] = [
                            {
                                "id": row.id,
                                "name": row.name,
                                "display_name": row.display_name,
                            }
                            for row in relationships_result.fetchall()
                        ]
                    except (ValueError, TypeError) as e:
                        logger.error("invalid_style_id", style_id=style_id, error=str(e))
                        context["dimensions"] = []
                        context["relationships"] = []
                        context["error"] = f"Invalid style_id: {style_id}"
                else:
                    context["dimensions"] = []
                    context["relationships"] = []

                # Handle POST requests
                if request.method == "POST":
                    form_data = await request.form()
                    action = form_data.get("action")

                    if action == "test_algorithm":
                        context["test_result"] = await self._handle_test_algorithm(form_data)
                        # Preserve form data for re-rendering
                        context["form_data"] = dict(form_data)

            return templates.TemplateResponse("custom_views/ai_score_test.html", context)

        except Exception as e:
            logger.error("ai_score_test_render_failed", error=str(e), exc_info=True)
            return templates.TemplateResponse(
                "custom_views/ai_score_test.html",
                {
                    "request": request,
                    "algorithm_info": {
                        1: get_algorithm_info(1),
                        2: get_algorithm_info(2),
                    },
                    "error": f"Failed to render score test interface: {str(e)}",
                },
            )

    async def _handle_test_algorithm(self, form_data) -> Dict[str, Any]:
        """Handle score algorithm testing - direct call to utility functions."""
        try:
            # Get basic parameters
            raw_algorithm = form_data.get("algorithm")
            if raw_algorithm is None:
                return {"success": False, "message": "Missing required field: algorithm"}
            algorithm = int(raw_algorithm)

            style_id_val = form_data.get("style_id")
            if not style_id_val:
                return {"success": False, "message": "Missing Style ID parameter"}
            style_id = int(style_id_val)

            current_relationship_id: Optional[int] = None
            current_relationship_name: Optional[str] = None
            raw_current_rel = form_data.get("current_relationship")
            if raw_current_rel:
                try:
                    current_relationship_id = int(raw_current_rel)
                except ValueError:
                    return {
                        "success": False,
                        "message": "Invalid current_relationship value",
                    }

            # Parse algorithm parameters
            params: Dict[str, Any] = {}
            if algorithm == 2:  # V1 algorithm
                left_bias_str = form_data.get("left_bias")
                right_bias_str = form_data.get("right_bias")

                if left_bias_str is None or right_bias_str is None:
                    return {
                        "success": False,
                        "message": "Missing required V1 parameters: left_bias, right_bias",
                    }
                try:
                    params["left_bias"] = int(left_bias_str)
                    params["right_bias"] = int(right_bias_str)
                except (TypeError, ValueError):
                    return {
                        "success": False,
                        "message": "Invalid V1 parameters: left_bias and right_bias must be integers",
                    }

                # Validate parameters
                if not validate_algorithm_params(algorithm, params):
                    return {
                        "success": False,
                        "message": "Algorithm parameters validation failed",
                    }

            # Get dimensions from database
            async with SessionLocal() as db:
                dimensions_result = await db.execute(
                    text(
                        """
                        SELECT name, display_name, initial_position
                        FROM ai_relationship_dimensions
                        WHERE style_id = :style_id
                        ORDER BY name
                        """
                    ),
                    {"style_id": style_id},
                )
                dimensions = dimensions_result.fetchall()

                if not dimensions:
                    return {"success": False, "message": "No dimensions configured for this style"}

                # Process each dimension
                dimension_results: List[Dict[str, Any]] = []

                for dim in dimensions:
                    # Get per-dimension score configuration
                    score_key = f"score_{dim.name}"
                    score_min_key = f"score_min_{dim.name}"
                    score_max_key = f"score_max_{dim.name}"

                    raw_score = form_data.get(score_key)
                    raw_min = form_data.get(score_min_key)
                    raw_max = form_data.get(score_max_key)

                    if raw_score is None or raw_min is None or raw_max is None:
                        return {
                            "success": False,
                            "message": f"Missing score fields for dimension {dim.display_name}",
                        }

                    try:
                        score = float(raw_score)
                        score_min = float(raw_min)
                        score_max = float(raw_max)
                    except (TypeError, ValueError):
                        return {
                            "success": False,
                            "message": f"Invalid score values for dimension {dim.display_name}",
                        }

                    # Validate per-dimension score range
                    if score_max <= score_min:
                        return {
                            "success": False,
                            "message": f"Score max must be greater than score min for dimension {dim.display_name}",
                        }

                    # Map score to 0-1000 range
                    mapped_position = ((score - score_min) / (score_max - score_min)) * 1000.0
                    mapped_position = max(0.0, min(1000.0, mapped_position))

                    # Apply algorithm directly using utility function
                    final_position = apply_score_algorithm(
                        algorithm, mapped_position, dim.initial_position, params
                    )

                    # Step 4: Find relationship candidates for this dimension
                    candidates_result = await db.execute(
                        text(
                            """
                            SELECT DISTINCT
                                ari.relationship_id,
                                ari.priority,
                                ari.start_position,
                                ari.end_position,
                                ar.name as relationship_name,
                                ar.display_name as relationship_display_name,
                                ar.prompt_fragment
                            FROM ai_relationship_indexes ari
                            JOIN ai_relationships ar ON ari.relationship_id = ar.id
                            WHERE ari.style_id = :style_id
                              AND ari.dimension_id = :dimension_id
                              AND ari.start_position <= :position
                              AND ari.end_position >= :position
                            ORDER BY ari.priority DESC
                            """
                        ),
                        {"style_id": style_id, "dimension_id": dim.id, "position": final_position},
                    )
                    candidates = candidates_result.fetchall()

                    dimension_results.append(
                        {
                            "dimension_name": dim.name,
                            "dimension_display_name": dim.display_name,
                            "input_score": score,
                            "score_min": score_min,
                            "score_max": score_max,
                            "mapped_position": mapped_position,
                            "initial_position": dim.initial_position,
                            "final_position": final_position,
                            "offset": final_position - mapped_position,
                            "candidates": [
                                {
                                    "relationship_id": c.relationship_id,
                                    "relationship_name": c.relationship_name,
                                    "relationship_display_name": c.relationship_display_name,
                                    "prompt_fragment": c.prompt_fragment,
                                    "priority": c.priority,
                                    "start_position": c.start_position,
                                    "end_position": c.end_position,
                                }
                                for c in candidates
                            ],
                        }
                    )

                # Step 5: Skip limit_count filtering (as per spec: "测试时忽略ai_relationship_indexes.limit_count的影响")

                # Step 6: Select final relationship
                # Find all unique relationships and their max priority across all dimensions
                all_candidates: Dict[int, Dict[str, Any]] = {}
                for result in dimension_results:
                    for candidate in result["candidates"]:
                        rel_id = candidate["relationship_id"]
                        if rel_id not in all_candidates:
                            all_candidates[rel_id] = {
                                "relationship_id": rel_id,
                                "relationship_name": candidate["relationship_name"],
                                "relationship_display_name": candidate["relationship_display_name"],
                                "prompt_fragment": candidate["prompt_fragment"],
                                "count": 0,
                                "max_priority": 0,
                            }
                        all_candidates[rel_id]["count"] += 1
                        all_candidates[rel_id]["max_priority"] = max(
                            all_candidates[rel_id]["max_priority"], candidate["priority"]
                        )

                # All unique candidates (already deduplicated in all_candidates dict)
                all_unique_candidates = list(all_candidates.values())

                # Select final relationship from all unique candidates
                selected_relationship: Optional[Dict[str, Any]] = None
                relationship_changed = False
                selection_reason = ""

                if all_unique_candidates:
                    # Check if current relationship is in candidates
                    if current_relationship_id:
                        current_in_candidates = any(
                            r["relationship_id"] == current_relationship_id for r in all_unique_candidates
                        )
                        if current_in_candidates:
                            # Current relationship has highest priority (special rule)
                            selected_relationship = next(
                                r
                                for r in all_unique_candidates
                                if r["relationship_id"] == current_relationship_id
                            )
                            relationship_changed = False
                            selection_reason = "Current relationship maintained (special rule: current relationship has priority)"
                        else:
                            # Select highest priority from all candidates
                            selected_relationship = max(
                                all_unique_candidates, key=lambda r: r["max_priority"]
                            )
                            relationship_changed = True
                            selection_reason = (
                                "Relationship changed (current relationship not in candidates)"
                            )
                    else:
                        # No current relationship, select highest priority
                        selected_relationship = max(all_unique_candidates, key=lambda r: r["max_priority"])
                        relationship_changed = False
                        selection_reason = (
                            "New relationship selected (highest priority from all candidates)"
                        )
                else:
                    selection_reason = "No relationship candidates found in any dimension"

                # Get algorithm info
                algo_info = get_algorithm_info(algorithm)

                return {
                    "success": True,
                    "algorithm_info": algo_info,
                    "parameters": params,
                    "dimension_results": dimension_results,
                    "selected_relationship": selected_relationship,
                    "all_unique_candidates": all_unique_candidates,
                    "all_candidates": list(all_candidates.values()),
                    "relationship_changed": relationship_changed,
                    "selection_reason": selection_reason,
                    "current_relationship_id": current_relationship_id,
                    "current_relationship_name": current_relationship_name,
                }

        except Exception as e:
            logger.error("ai_score_algorithm_test_failed", error=str(e))
            return {"success": False, "message": f"Algorithm test failed: {str(e)}"}


# Create view instances with updated configuration
ai_character_chat_test_view = AICharacterChatTestView(
    label="Character Chat Test",
    icon="",
    path="/ai-character/{id:int}/chat-test",
    methods=["GET", "POST"],  # Allow both GET and POST
    add_to_menu=False,  # Accessed via row actions only
)

ai_score_algorithm_test_view = AIScoreAlgorithmTestView(
    label="Score Algorithm Test",
    icon="",
    path="/ai-style/{id:int}/score-algorithm-test",
    methods=["GET", "POST"],
    add_to_menu=False,  # Accessed via row actions only
)


class AIRelationshipIndexAPIView(CustomView):
    """API endpoint for relationship indexes."""

    def is_accessible(self, _request: Request) -> bool:
        """Allow access to this view."""
        return True

    async def render(self, request: Request, _templates: Jinja2Templates) -> Response:
        """Handle API requests for relationship indexes."""
        try:
            style_id = request.query_params.get("style_id")
            limit = int(request.query_params.get("limit", 100))

            if not style_id:
                return JSONResponse(
                    {"error": "Missing style_id parameter"},
                    status_code=400,
                )

            async with SessionLocal() as db:
                # Get relationship indexes for the specific style, filtering by existing dimensions
                query = """
                SELECT DISTINCT
                    ari.relationship_id,
                    ari.dimension_id,
                    ard.name as dimension_name,
                    ari.start_position,
                    ari.end_position,
                    ari.priority,
                    ar.name as relationship_name,
                    ar.display_name as relationship_display_name
                FROM ai_relationship_indexes ari
                JOIN ai_relationship_dimensions ard ON ard.id = ari.dimension_id AND ard.style_id = :style_id
                JOIN ai_relationships ar ON ar.id = ari.relationship_id
                WHERE ari.style_id = :style_id
                ORDER BY ard.name, ari.start_position
                LIMIT :limit
                """

                result = await db.execute(text(query), {"style_id": int(style_id), "limit": limit})
                rows = result.fetchall()

                items = []
                for row in rows:
                    items.append(
                        {
                            "relationship_id": row.relationship_id,
                            "dimension_name": row.dimension_name,
                            "start_position": row.start_position,
                            "end_position": row.end_position,
                            "priority": row.priority,
                            "relationship_name": row.relationship_name,
                            "relationship_display_name": row.relationship_display_name,
                        }
                    )

                return JSONResponse({"items": items, "total": len(items), "style_id": style_id})

        except Exception as e:
            logger.error(
                "relationship_indexes_api_failed",
                error=str(e),
                style_id=request.query_params.get("style_id"),
            )
            return JSONResponse(
                {"error": f"Failed to get relationship indexes: {str(e)}"},
                status_code=500,
            )


ai_relationship_index_api_view = AIRelationshipIndexAPIView(
    label="Relationship Index API",
    icon="fas fa-api",
    path="/api/relationship_indexes",
    methods=["GET"],  # Only GET method
    add_to_menu=False,  # Do not show in menu - API only
)

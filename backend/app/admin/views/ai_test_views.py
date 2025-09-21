"""
AI character testing views for admin panel.

This module provides admin interface for testing AI characters
with different users and LLM configurations.
"""

import uuid
from typing import Dict, Any, List, Optional
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView
from sqlalchemy import text

from core.database import SessionLocal
from services.admin.test_users import default_test_user_service
from services.llm.config import default_llm_config_service
from services.ai.data import get_all_characters
from services.ai.conversation import process_conversation
from services.ai.utils.score_algorithm import (
    apply_score_algorithm,
    get_algorithm_info,
    validate_algorithm_params,
)
from services.ai.relationship import get_relationship_scores
from services.llm.request_logger import default_request_logger
from utils.logging import get_logger

logger = get_logger(__name__)

# Initialize templates with relative path
templates = Jinja2Templates(directory="admin/templates")


class AICharacterChatTestView(CustomView):
    """AI Character Chat Test interface."""

    def is_accessible(self, request: Request) -> bool:
        """Allow access to this view."""
        return True

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the AI character chat test interface."""
        try:
            # Get character_id from URL parameters
            character_id = request.query_params.get("character_id")

            # Initialize variables
            test_users = []
            llm_config_options = []
            character_options = []
            characters = []
            selected_character = None

            # Get database session
            async with SessionLocal() as db:
                # Get test users
                test_users = await default_test_user_service.get_test_users_for_selection(db)

                # Get LLM configs
                llm_configs = await default_llm_config_service.get_active_configs(db)
                llm_config_options = [
                    {
                        "value": config["config_key"],
                        "label": f"{config['config_key']} ({config['model_name']})",
                    }
                    for config in llm_configs
                ]

                # Get AI characters
                characters = await get_all_characters(db)
                character_options = [
                    {
                        "value": char["qiao_id"],
                        "label": f"{char['name']} ({char['qiao_id']})",
                    }
                    for char in characters
                ]

            # Parse character_id from query parameters (single character)
            selected_character_id = request.query_params.get("character_id", "")
            selected_character_info = None

            # Get detailed info for selected character
            if selected_character_id:
                for char in characters:
                    if char["qiao_id"] == selected_character_id:
                        selected_character_info = char
                        break

            context = {
                "request": request,
                "test_users": test_users,
                "llm_configs": llm_config_options,
                "characters": character_options,
                "selected_character_id": selected_character_id,
                "selected_character_info": selected_character_info,
                "page_title": "AI Character Chat Test",
            }

            return templates.TemplateResponse("custom_views/ai_character_chat_test.html", context)

        except Exception as e:
            logger.error(
                "ai_character_chat_test_render_failed",
                error=str(e),
            )
            return JSONResponse(
                {"error": "Failed to load AI character chat test interface"},
                status_code=500,
            )

    async def handle_test_request(self, request: Request) -> JSONResponse:
        """Handle AI character test request."""
        try:
            # Parse request data
            form_data = await request.form()
            character_qiao_id = form_data.get("character_qiao_id")
            user_qiao_id = form_data.get("user_qiao_id")
            llm_config_key = form_data.get("llm_config_key")
            test_message = form_data.get("test_message", "Hello, how are you today?")  # real or simulated

            # Validate required fields
            if not all([character_qiao_id, user_qiao_id, llm_config_key]):
                return JSONResponse(
                    {"error": "Missing required fields: character_qiao_id, user_qiao_id, llm_config_key"},
                    status_code=400,
                )

            # Generate test session ID
            test_session_id = str(uuid.uuid4())

            async with SessionLocal() as db:
                # Validate test user
                is_valid_user = await default_test_user_service.validate_test_user(db, user_qiao_id)
                if not is_valid_user:
                    return JSONResponse(
                        {"error": f"Invalid test user: {user_qiao_id}"},
                        status_code=400,
                    )

                # Start request logging
                request_id = await default_request_logger.start_request_log(
                    db=db,
                    character_qiao_id=character_qiao_id,
                    user_qiao_id=user_qiao_id,
                    config_key=llm_config_key,
                    test_session_id=test_session_id,
                    request_data={
                        "message": test_message,
                        "character_qiao_id": character_qiao_id,
                        "user_qiao_id": user_qiao_id,
                        "llm_config_key": llm_config_key,
                    },
                )

                try:
                    # Process AI conversation using configured LLM
                    import time

                    start_time = time.time()

                    conversation_result = await process_conversation(
                        db=db,
                        user_qiao_id=user_qiao_id,
                        character_qiao_id=character_qiao_id,
                        message_content=test_message,
                    )

                    end_time = time.time()
                    response_time_ms = int((end_time - start_time) * 1000)

                    # Complete request log
                    await default_request_logger.complete_request_log(
                        db=db,
                        request_id=request_id,
                        response_data=conversation_result,
                        response_time_ms=response_time_ms,
                        status="success",
                    )

                    result = {
                        "success": True,
                        "request_id": request_id,
                        "test_session_id": test_session_id,
                        "response": conversation_result,
                        "response_time_ms": response_time_ms,
                    }

                    logger.info(
                        "ai_character_test_completed",
                        character_qiao_id=character_qiao_id,
                        user_qiao_id=user_qiao_id,
                        test_session_id=test_session_id,
                    )

                    return JSONResponse(result)

                except Exception as conversation_error:
                    # Complete request log with error
                    await default_request_logger.complete_request_log(
                        db=db,
                        request_id=request_id,
                        status="error",
                        error_message=str(conversation_error),
                    )

                    logger.error(
                        "ai_character_test_conversation_failed",
                        error=str(conversation_error),
                        character_qiao_id=character_qiao_id,
                        user_qiao_id=user_qiao_id,
                    )

                    return JSONResponse(
                        {
                            "success": False,
                            "error": f"Conversation processing failed: {str(conversation_error)}",
                            "request_id": request_id,
                            "test_session_id": test_session_id,
                        },
                        status_code=500,
                    )

        except Exception as e:
            logger.error(
                "ai_character_test_request_failed",
                error=str(e),
            )
            return JSONResponse(
                {"error": f"Test request failed: {str(e)}"},
                status_code=500,
            )

    async def get_test_logs(self, request: Request) -> JSONResponse:
        """Get test session logs."""
        try:
            test_session_id = request.query_params.get("test_session_id")
            if not test_session_id:
                return JSONResponse(
                    {"error": "Missing test_session_id parameter"},
                    status_code=400,
                )

            async with SessionLocal() as db:
                # Get request logs
                logs = await default_request_logger.get_request_logs(
                    db=db,
                    test_session_id=test_session_id,
                    limit=50,
                )

                # Get session summary
                summary = await default_request_logger.get_test_session_summary(db, test_session_id)

                result = {
                    "test_session_id": test_session_id,
                    "summary": summary,
                    "logs": [log.to_dict() for log in logs],
                }

                return JSONResponse(result)

        except Exception as e:
            logger.error(
                "ai_character_test_logs_failed",
                error=str(e),
            )
            return JSONResponse(
                {"error": f"Failed to get test logs: {str(e)}"},
                status_code=500,
            )


class AIScoreAlgorithmTestView(CustomView):
    """AI Score Algorithm Test interface."""

    def is_accessible(self, request: Request) -> bool:
        """Allow access to this view."""
        return True

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the AI score algorithm test interface."""
        try:
            # Get style_id from URL parameters
            style_id = request.query_params.get("style_id")

            context = {
                "request": request,
                "algorithm_info": {},
                "character_options": [],
                "test_result": None,
                "character_scores": None,
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
                # Get all characters for testing
                characters = await get_all_characters(db)
                context["character_options"] = [
                    {
                        "qiao_id": char["qiao_id"],
                        "name": char["name"],
                        "nickname": char.get("nickname", ""),  # Use get() to handle missing nickname
                    }
                    for char in characters
                ]

                # Get dimensions and relationships for the selected style
                if style_id:
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
                    context["dimensions"] = [
                        {
                            "name": row.name,
                            "display_name": row.display_name,
                            "initial_position": row.initial_position,
                        }
                        for row in dimensions_result.fetchall()
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
                else:
                    context["dimensions"] = []
                    context["relationships"] = []

                # Handle POST requests
                if request.method == "POST":
                    form_data = await request.form()
                    action = form_data.get("action")

                    if action == "test_algorithm":
                        context["test_result"] = await self._handle_test_algorithm(form_data)
                    elif action == "get_character_scores":
                        context["character_scores"] = await self._handle_character_scores(db, form_data)

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
                    "character_options": [],
                    "error": f"Failed to render score test interface: {str(e)}",
                },
            )

    async def _handle_test_algorithm(self, form_data) -> Dict[str, Any]:
        """Handle score algorithm testing with multi-dimension support."""
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

            # Parse algorithm parameters (no silent defaults)
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

            # Get dimensions and their scores from form data
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

                # Validate current relationship name if provided
                if current_relationship_id is not None:
                    rel_res = await db.execute(
                        text("SELECT display_name FROM ai_relationships WHERE id = :id"),
                        {"id": current_relationship_id},
                    )
                    row = rel_res.first()
                    current_relationship_name = row.display_name if row else None

                # Process each dimension with its own score range
                dimension_results: List[Dict[str, Any]] = []
                all_relationship_candidates: List[Dict[str, Any]] = (
                    []
                )  # Store candidates from all dimensions

                for dim in dimensions:
                    # Get per-dimension score configuration (no server-side defaults)
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

                    # First map score to 0-1000 range
                    mapped_position = ((score - score_min) / (score_max - score_min)) * 1000.0
                    mapped_position = max(0.0, min(1000.0, mapped_position))

                    # Then apply algorithm with mapped score
                    final_position = apply_score_algorithm(
                        algorithm, mapped_position, dim.initial_position, params
                    )

                    # Calculate detailed debugging information
                    score_range = score_max - score_min
                    score_offset_from_min = score - score_min
                    mapping_ratio = score_offset_from_min / score_range if score_range > 0 else 0.0
                    position_offset_from_initial = final_position - dim.initial_position
                    algorithm_applied_offset = final_position - mapped_position

                    # Find candidate relationships for this dimension (restrict to selected style)
                    candidates = await self._find_relationship_candidates_by_position(
                        style_id, dim.name, final_position
                    )
                    all_relationship_candidates.extend(candidates)

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
                            "candidates": candidates,
                            "debug_info": {
                                "score_range": score_range,
                                "score_offset_from_min": score_offset_from_min,
                                "mapping_ratio": mapping_ratio,
                                "position_offset_from_initial": position_offset_from_initial,
                                "algorithm_applied_offset": algorithm_applied_offset,
                            },
                        }
                    )

                # Relationship selection according to documentation
                selected_relationship = await self._select_final_relationship(
                    all_relationship_candidates, current_relationship_id
                )

                # Enhance selected relationship with candidate summary
                unique_relationship_ids = {c.get("relationship_id") for c in all_relationship_candidates}
                selected_relationship["candidate_relationships"] = len(unique_relationship_ids)
                # partial_matches is optional and UI tolerates absence; keep as empty list for clarity
                selected_relationship["partial_matches"] = []

                # Update dimension results with selected relationship
                for result in dimension_results:
                    result["relationship"] = selected_relationship
                    result["debug_info"]["relationship_position_range"] = selected_relationship.get(
                        "position_range", "N/A"
                    )

                # Get algorithm info for display from services layer
                algo_info = get_algorithm_info(algorithm)

                # Relationship change status (only if current is provided and valid)
                relationship_changed: Optional[bool] = None
                if (
                    current_relationship_id is not None
                    and selected_relationship.get("relationship_id") is not None
                ):
                    relationship_changed = (
                        selected_relationship["relationship_id"] != current_relationship_id
                    )

                return {
                    "success": True,
                    "algorithm_info": algo_info,
                    "parameters": params,
                    "dimension_results": dimension_results,
                    "current_relationship_id": current_relationship_id,
                    "current_relationship_name": current_relationship_name,
                    "relationship_changed": relationship_changed,
                }

        except Exception as e:
            logger.error("ai_score_algorithm_test_failed", error=str(e))
            return {"success": False, "message": f"Algorithm test failed: {str(e)}"}

    async def _find_relationship_candidates_by_position(
        self, style_id: int, dimension_name: str, position: float
    ) -> List[Dict[str, Any]]:
        """Find all candidate relationships for a dimension position"""
        try:
            async with SessionLocal() as db:
                query = """
                SELECT DISTINCT
                    ari.relationship_id,
                    ari.dimension_name,
                    ari.start_position,
                    ari.end_position,
                    ari.priority,
                    ar.display_name,
                    ar.prompt_fragment
                FROM ai_relationship_indexes ari
                JOIN ai_relationships ar ON ari.relationship_id = ar.id
                WHERE ari.style_id = :style_id
                AND ari.dimension_name = :dimension_name
                AND :position BETWEEN ari.start_position AND ari.end_position
                ORDER BY ari.priority ASC
                """

                from sqlalchemy import text

                result = await db.execute(
                    text(query),
                    {"style_id": int(style_id), "dimension_name": dimension_name, "position": position},
                )
                rows = result.fetchall()

                candidates = []
                for row in rows:
                    candidates.append(
                        {
                            "relationship_id": row.relationship_id,
                            "dimension_name": row.dimension_name,
                            "display_name": row.display_name,
                            "prompt_fragment": row.prompt_fragment,
                            "position_range": f"{row.start_position}-{row.end_position}",
                            "priority": row.priority,
                        }
                    )

                return candidates

        except Exception as e:
            logger.error("relationship_candidates_lookup_failed", error=str(e))
            return []

    async def _select_final_relationship(
        self, all_candidates: List[Dict[str, Any]], current_relationship_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Select final relationship according to documentation requirements"""
        try:
            if not all_candidates:
                return {
                    "display_name": "No Match",
                    "prompt_fragment": "No relationships found",
                    "position_range": "N/A",
                    "selection_reason": "No candidates found",
                }

            # 1. Special rule: if current relationship is among candidates, prioritize it
            if current_relationship_id:
                for candidate in all_candidates:
                    if candidate["relationship_id"] == current_relationship_id:
                        candidate["selection_reason"] = "Current relationship prioritized"
                        logger.info(
                            "current_relationship_prioritized_in_test",
                            current_relationship_id=current_relationship_id,
                            relationship_name=candidate["display_name"],
                            total_candidates=len(all_candidates),
                        )
                        return candidate

            # 2. Sort by priority (higher number = higher priority)
            sorted_candidates = sorted(all_candidates, key=lambda x: x["priority"], reverse=True)

            # 3. Check for priority conflicts
            highest_priority = sorted_candidates[0]["priority"]
            conflicts = [c for c in sorted_candidates if c["priority"] == highest_priority]

            if len(conflicts) > 1:
                # Log priority conflict but continue with first candidate
                conflict_ids = [c["relationship_id"] for c in conflicts]
                logger.warning(
                    "priority_conflict_detected_selecting_first",
                    priority=highest_priority,
                    conflicting_relationships=conflict_ids,
                    selected_relationship=conflicts[0]["relationship_id"],
                )
                selected = conflicts[0]
                selected["selection_reason"] = (
                    f"Priority conflict detected (priority {highest_priority}), selected first candidate among {len(conflicts)} conflicts"
                )
            else:
                selected = sorted_candidates[0]
                selected["selection_reason"] = (
                    f"Highest priority (priority {highest_priority}) among {len(all_candidates)} candidates"
                )

            return selected

        except Exception as e:
            logger.error("relationship_selection_failed", error=str(e))
            return {
                "display_name": "Selection Error",
                "prompt_fragment": f"Selection failed: {str(e)}",
                "position_range": "N/A",
                "selection_reason": "Error occurred during selection",
            }

    async def _handle_character_scores(self, db, form_data) -> Dict[str, Any]:
        """Handle getting character relationship scores."""
        try:
            character_qiao_id = form_data.get("character_qiao_id")

            if not character_qiao_id:
                return {"error": "Character qiao_id is required"}

            scores = await get_relationship_scores(db, character_qiao_id)

            return {
                "success": True,
                "scores": scores,
            }

        except Exception as e:
            logger.error("ai_character_scores_failed", error=str(e))
            return {"error": f"Failed to get character scores: {str(e)}"}


class AIRelationshipIndexAPIView(CustomView):
    """API endpoint for relationship indexes."""

    def is_accessible(self, request: Request) -> bool:
        """Allow access to this view."""
        return True

    async def render(self, request: Request, templates: Jinja2Templates) -> JSONResponse:
        """Return relationship indexes as JSON."""
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
                    ari.dimension_name,
                    ari.start_position,
                    ari.end_position,
                    ari.priority,
                    ar.name as relationship_name,
                    ar.display_name as relationship_display_name
                FROM ai_relationship_indexes ari
                JOIN ai_relationship_dimensions ard ON ard.name = ari.dimension_name AND ard.style_id = :style_id
                JOIN ai_relationships ar ON ar.id = ari.relationship_id
                WHERE ari.style_id = :style_id
                ORDER BY ari.dimension_name, ari.start_position
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


# Create view instances
ai_character_chat_test_view = AICharacterChatTestView(
    label="Character Chat Test",
    icon="fas fa-robot",
    path="/ai-character-chat-test",
    add_to_menu=False,  # Do not show in menu - accessed via row actions only
)

ai_score_algorithm_test_view = AIScoreAlgorithmTestView(
    label="Score Algorithm Test",
    icon="fas fa-calculator",
    path="/ai-score-algorithm-test",
    methods=["GET", "POST"],  # Allow both GET and POST methods
    add_to_menu=False,  # Do not show in menu - accessed via row actions only
)

ai_relationship_index_api_view = AIRelationshipIndexAPIView(
    label="Relationship Index API",
    icon="fas fa-api",
    path="/api/relationship_indexes",
    methods=["GET"],  # Only GET method
    add_to_menu=False,  # Do not show in menu - API only
)

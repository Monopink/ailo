"""
AI character testing views for admin panel.

This module provides admin interface for testing AI characters
with different users and LLM configurations.
"""

import uuid
from typing import Dict, Any
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from core.database import SessionLocal
from services.admin.test_users import default_test_user_service
from services.llm.config import default_llm_config_service
from services.ai.data import get_all_characters
from services.ai.conversation import process_conversation
from services.ai.utils.score_algorithm import (
    apply_score_algorithm,
    get_algorithm_info,
    validate_algorithm_params,
    ScoreOffsetAlgorithm,
)
from services.ai.relationship import get_relationship_scores
from services.llm.request_logger import default_request_logger
from utils.logging import get_logger

logger = get_logger(__name__)

# Initialize templates with relative path
templates = Jinja2Templates(directory="admin/templates")


class AICharacterChatTestView(CustomView):
    """AI Character Chat Test interface."""

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
            }

            # Get algorithm information
            for algorithm in ScoreOffsetAlgorithm:
                context["algorithm_info"][algorithm.value] = get_algorithm_info(algorithm.value)

            # Get database session
            async with SessionLocal() as db:
                # Get all characters for testing
                characters = await get_all_characters(db)
                context["character_options"] = [
                    {
                        "qiao_id": char["qiao_id"],
                        "name": char["name"],
                        "nickname": char["nickname"],
                    }
                    for char in characters
                ]

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
            logger.error("ai_score_test_render_failed", error=str(e))
            return templates.TemplateResponse(
                "custom_views/ai_score_test.html",
                {
                    "request": request,
                    "algorithm_info": {},
                    "character_options": [],
                    "error": f"Failed to render score test interface: {str(e)}",
                },
            )

    async def _handle_test_algorithm(self, form_data) -> Dict[str, Any]:
        """Handle score algorithm testing."""
        try:
            # Get test parameters
            algorithm = int(form_data.get("algorithm", 0))
            score = float(form_data.get("score", 500))
            initial_position = float(form_data.get("initial_position", 500))

            # Parse algorithm parameters
            params = {}
            if algorithm == ScoreOffsetAlgorithm.V1.value:
                params["strength"] = float(form_data.get("strength", 0.5))

            # Validate parameters
            if not validate_algorithm_params(algorithm, params):
                return {"error": "Invalid algorithm parameters"}

            # Apply algorithm
            result = apply_score_algorithm(algorithm, score, initial_position, params)

            # Get algorithm info for display
            algo_info = get_algorithm_info(algorithm)

            return {
                "success": True,
                "input_score": score,
                "initial_position": initial_position,
                "final_position": result,
                "offset": result - initial_position,
                "algorithm_info": algo_info,
                "parameters": params,
            }

        except Exception as e:
            logger.error("ai_score_algorithm_test_failed", error=str(e))
            return {"error": f"Algorithm test failed: {str(e)}"}

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


# Create view instances
ai_character_chat_test_view = AICharacterChatTestView(
    label="AI Character Chat Test",
    icon="fas fa-robot",
    path="/ai-character-chat-test",
    add_to_menu=True,  # Show in menu
)

ai_score_algorithm_test_view = AIScoreAlgorithmTestView(
    label="AI Score Algorithm Test",
    icon="fas fa-calculator",
    path="/ai-score-algorithm-test",
    add_to_menu=True,  # Show in menu
)

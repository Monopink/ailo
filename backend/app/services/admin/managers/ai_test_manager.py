"""
AI Test Manager.
Manages AI testing business processes including conversation testing,
algorithm testing, and prompt preview functionality.
"""

import uuid
import time
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai.conversation import process_conversation
from services.ai.data import get_character_with_relations
from services.ai.utils.score_algorithm import (
    apply_score_algorithm,
    get_algorithm_info,
    validate_algorithm_params,
)
from services.llm.request_logger import default_request_logger
from ..utils.validation_utils import (
    validate_chat_test_request,
    validate_algorithm_test_request,
    validate_batch_test_config,
)
from ..utils.calculation_utils import (
    calculate_batch_algorithm_results,
    calculate_algorithm_details,
)
from utils.logging import get_logger

logger = get_logger(__name__)


class AITestManager:
    """
    Manages AI testing business processes.

    Handles state management, resource management, and error handling
    for AI-related testing operations.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize AI test manager.

        Args:
            db: Database session
        """
        self.db = db
        self.request_logger = default_request_logger

    async def test_character_chat(
        self,
        character_qiao_id: str,
        user_qiao_id: str,
        llm_config_key: str,
        test_message: str,
        enable_thinking: bool = True,
        test_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Test AI character chat functionality.

        Manages the complete AI conversation testing process including
        request logging, conversation processing, and result formatting.

        Args:
            character_qiao_id: Character's qiao_id
            user_qiao_id: Test user's qiao_id
            llm_config_key: LLM configuration key
            test_message: Test message content
            enable_thinking: Enable thinking mode
            test_session_id: Optional test session ID

        Returns:
            Test result with conversation data and performance metrics

        Raises:
            ValueError: If validation fails
            Exception: If test execution fails
        """
        # Validate request parameters
        validation_errors = validate_chat_test_request(
            character_qiao_id, user_qiao_id, llm_config_key, test_message
        )
        if validation_errors:
            raise ValueError(f"Validation failed: {', '.join(validation_errors)}")

        # Generate test session ID if not provided
        if not test_session_id:
            test_session_id = str(uuid.uuid4())

        request_id = None

        try:
            # Create request log
            request_id = await self.request_logger.create_request_log(
                db=self.db,
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
                llm_config_key=llm_config_key,
                test_session_id=test_session_id,
            )

            logger.info(
                "ai_character_test_started",
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
                test_session_id=test_session_id,
                request_id=request_id,
            )

            # Process AI conversation
            start_time = time.time()

            conversation_result = await process_conversation(
                db=self.db,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                message_content=test_message,
            )

            end_time = time.time()
            response_time_ms = int((end_time - start_time) * 1000)

            # Complete request log
            await self.request_logger.complete_request_log(
                db=self.db,
                request_id=request_id,
                response_data=conversation_result,
                response_time_ms=response_time_ms,
                status="success",
            )

            # Format result
            result = {
                "test_session_id": test_session_id,
                "request_id": request_id,
                "conversation_result": {
                    "ai_response": conversation_result.get("ai_response", ""),
                    "thinking_process": conversation_result.get("thinking_process", ""),
                    "score_updates": conversation_result.get("score_updates", {}),
                    "memory_operations": conversation_result.get("memory_operations", []),
                    "should_reply": conversation_result.get("should_reply", True),
                    "attack_detected": conversation_result.get("attack_detected", False),
                },
                "performance": {
                    "response_time_ms": response_time_ms,
                    "token_usage": conversation_result.get("token_usage", {}),
                },
                "config_used": conversation_result.get("config_used", {}),
            }

            logger.info(
                "ai_character_test_completed",
                character_qiao_id=character_qiao_id,
                test_session_id=test_session_id,
                response_time_ms=response_time_ms,
            )

            return result

        except Exception as e:
            # Handle errors and update request log
            if request_id:
                try:
                    await self.request_logger.complete_request_log(
                        db=self.db,
                        request_id=request_id,
                        response_data={"error": str(e)},
                        response_time_ms=0,
                        status="failed",
                    )
                except Exception:
                    pass  # Don't fail on logging error

            logger.error(
                "ai_character_test_failed",
                character_qiao_id=character_qiao_id,
                test_session_id=test_session_id,
                error=str(e),
                exc_info=True,
            )

            raise

    async def test_score_algorithm(
        self,
        algorithm: int,
        score: float,
        initial_position: float,
        params: Dict[str, Any],
        batch_test: Optional[Dict[str, Any]] = None,
        current_relationship_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Test score offset algorithm with current relationship priority support.

        Args:
            algorithm: Algorithm type
            score: Input score
            initial_position: Initial position
            params: Algorithm parameters
            batch_test: Optional batch test configuration
            current_relationship_id: Current relationship ID for priority testing

        Returns:
            Algorithm test result with calculation details and relationship change info

        Raises:
            ValueError: If validation fails
            Exception: If test execution fails
        """
        # Validate request parameters
        validation_errors = validate_algorithm_test_request(algorithm, score, initial_position, params)
        if batch_test:
            validation_errors.extend(validate_batch_test_config(batch_test))

        if validation_errors:
            raise ValueError(f"Validation failed: {', '.join(validation_errors)}")

        try:
            # Validate algorithm parameters
            validate_algorithm_params(algorithm, params)

            # Apply algorithm for single test
            new_score = apply_score_algorithm(
                algorithm=algorithm,
                score=score,
                initial_position=initial_position,
                params=params,
            )

            # Get algorithm info
            algorithm_info = get_algorithm_info(algorithm)

            # Calculate details
            calculation_details = calculate_algorithm_details(score, initial_position, new_score, params)

            result = {
                "single_result": {
                    "new_score": new_score,
                    "offset": new_score - score,
                    "algorithm_name": algorithm_info["name"],
                },
                "calculation_details": calculation_details,
                "batch_results": None,
                "current_relationship_id": current_relationship_id,
                "relationship_changed": False,  # Will be updated by relationship selection logic
                "current_relationship_name": None,  # Will be populated if current_relationship_id exists
            }

            # Handle batch test if requested
            if batch_test and batch_test.get("enabled", False):
                batch_results = calculate_batch_algorithm_results(
                    algorithm=algorithm,
                    initial_position=initial_position,
                    params=params,
                    score_range=batch_test.get("score_range", [0, 1000]),
                    step=batch_test.get("step", 50),
                )
                result["batch_results"] = batch_results

            logger.info(
                "score_algorithm_test_completed",
                algorithm=algorithm,
                input_score=score,
                output_score=new_score,
                batch_enabled=batch_test is not None and batch_test.get("enabled", False),
            )

            return result

        except Exception as e:
            logger.error(
                "score_algorithm_test_failed",
                algorithm=algorithm,
                score=score,
                error=str(e),
                exc_info=True,
            )
            raise

    async def test_prompt_preview(
        self,
        character_qiao_id: str,
        user_qiao_id: str,
        relationship_override: Optional[Dict[str, Any]] = None,
        context_length: int = 10,
        include_thinking: bool = True,
    ) -> Dict[str, Any]:
        """
        Test prompt preview functionality.

        Args:
            character_qiao_id: Character's qiao_id
            user_qiao_id: Test user's qiao_id
            relationship_override: Optional relationship override
            context_length: Context length
            include_thinking: Include thinking prompt

        Returns:
            Prompt preview result with placeholder information

        Raises:
            ValueError: If validation fails
            Exception: If test execution fails
        """
        # Validate required parameters
        if not character_qiao_id or not character_qiao_id.strip():
            raise ValueError("character_qiao_id is required")
        if not user_qiao_id or not user_qiao_id.strip():
            raise ValueError("user_qiao_id is required")

        try:
            # Get character data
            character_data = await get_character_with_relations(self.db, character_qiao_id)
            if not character_data:
                raise ValueError(f"Character not found: {character_qiao_id}")

            character = character_data.get("character")
            if not character:
                raise ValueError(f"Character data invalid: {character_qiao_id}")

            # TODO: Implement actual prompt building logic
            # This is a placeholder implementation
            result = {
                "prompt_preview": {
                    "system_prompt": f"你是一个AI角色，名字是{character.name}...",
                    "user_context": "最近的对话历史...",
                    "thinking_prompt": "请分析用户的意图..." if include_thinking else None,
                    "full_prompt": "完整的合成提示词",
                },
                "placeholder_info": {
                    "total_placeholders": 15,
                    "replaced_count": 15,
                    "missing_placeholders": [],
                },
                "character_info": {
                    "qiao_id": character_qiao_id,
                    "name": character.name,
                    "current_relationship": "普通朋友",  # TODO: Get actual relationship
                },
            }

            logger.info(
                "prompt_preview_test_completed",
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
                context_length=context_length,
            )

            return result

        except Exception as e:
            logger.error(
                "prompt_preview_test_failed",
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
                error=str(e),
                exc_info=True,
            )
            raise

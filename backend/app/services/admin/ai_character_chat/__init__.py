"""
AI Character Chat Test Service - Facade

This module provides a unified interface for AI character chat testing,
combining validation, user matching, and execution services following
the facade pattern for clean separation of concerns.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .validation import validation_service, ValidationError
from .user_matcher import user_matcher_service, UserMatcherError
from .executor import executor_service, ExecutorError
from utils.logging import get_logger

logger = get_logger(__name__)


class AICharacterChatTestError(Exception):
    """Main exception for AI character chat test service"""

    def __init__(
        self, message: str, error_code: str = "CHAT_TEST_ERROR", suggestions: Optional[list] = None
    ):
        self.message = message
        self.error_code = error_code
        self.suggestions = suggestions or []
        super().__init__(message)


class AICharacterChatTestService:
    """
    Facade service for AI character chat testing.

    Orchestrates the complete test flow: validation -> user matching -> execution
    while maintaining stateless design and clear error handling.
    """

    async def prepare_and_execute_test(
        self,
        db: AsyncSession,
        character_id: int,
        llm_config_key: str,
        test_message: str,
    ) -> Dict[str, Any]:
        """
        Complete test flow: validate prerequisites, match test user, and execute test.

        Args:
            db: Database session
            character_id: AI character ID
            llm_config_key: LLM configuration key
            test_message: Test message content

        Returns:
            Dictionary containing test results and all relevant information

        Raises:
            AICharacterChatTestError: If any step fails
        """
        try:
            # Step 1: Validate all prerequisites
            logger.info("ai_chat_test_validation_start", character_id=character_id)
            validation_result = await validation_service.validate_character_test_prerequisites(
                db=db, character_id=character_id
            )

            # Step 2: Find and validate test user
            logger.info("ai_chat_test_user_matching_start", character_id=character_id)
            user_match_result = await user_matcher_service.find_test_user_for_character(
                db=db, character_info=validation_result["character"]
            )

            # Step 3: Execute test with main conversation logic
            logger.info(
                "ai_chat_test_execution_start",
                character_id=character_id,
                test_user_qiao_id=user_match_result["test_user"]["qiao_id"],
            )
            execution_result = await executor_service.execute_character_chat_test(
                db=db,
                character_qiao_id=validation_result["character"]["qiao_id"],
                user_qiao_id=user_match_result["test_user"]["qiao_id"],
                llm_config_key=llm_config_key,
                test_message=test_message,
            )

            # Combine all results for comprehensive response
            complete_result = {
                "test_execution": execution_result,
                "validation_info": {
                    "character": validation_result["character"],
                    "character_profile": validation_result["character_profile"],
                    "style": validation_result["style"],
                    "personality": validation_result["personality"],
                    "relationship_scores": validation_result["relationship_scores"],
                },
                "test_user_info": {
                    "test_user": user_match_result["test_user"],
                    "test_user_profile": user_match_result["test_user_profile"],
                },
                "available_llm_configs": validation_result["llm_configs"],
            }

            logger.info(
                "ai_chat_test_complete_success",
                character_id=character_id,
                response_time_ms=execution_result["performance"]["response_time_ms"],
            )

            return complete_result

        except ValidationError as e:
            logger.error("ai_chat_test_validation_failed", character_id=character_id, error=str(e))
            raise AICharacterChatTestError(
                f"Test validation failed: {e.message}",
                error_code=e.error_code,
                suggestions=e.suggestions,
            )

        except UserMatcherError as e:
            logger.error("ai_chat_test_user_matching_failed", character_id=character_id, error=str(e))
            raise AICharacterChatTestError(
                f"Test user matching failed: {e.message}",
                error_code=e.error_code,
                suggestions=e.suggestions,
            )

        except ExecutorError as e:
            logger.error("ai_chat_test_execution_failed", character_id=character_id, error=str(e))
            raise AICharacterChatTestError(
                f"Test execution failed: {e.message}",
                error_code=e.error_code,
            )

        except Exception as e:
            logger.error(
                "ai_chat_test_unexpected_error", character_id=character_id, error=str(e), exc_info=True
            )
            raise AICharacterChatTestError(
                f"Unexpected error during test: {str(e)}",
                error_code="UNEXPECTED_ERROR",
            )

    async def validate_test_readiness(self, db: AsyncSession, character_id: int) -> Dict[str, Any]:
        """
        Check test readiness without executing the test.

        Args:
            db: Database session
            character_id: AI character ID

        Returns:
            Dictionary containing validation status and prerequisites info

        Raises:
            AICharacterChatTestError: If validation fails
        """
        try:
            # Validate prerequisites
            validation_result = await validation_service.validate_character_test_prerequisites(
                db=db, character_id=character_id
            )

            # Check test user availability
            user_match_result = await user_matcher_service.find_test_user_for_character(
                db=db, character_info=validation_result["character"]
            )

            return {
                "ready": True,
                "character_info": {
                    "qiao_id": validation_result["character"]["qiao_id"],
                    "category": validation_result["character"]["category"],
                    "style": validation_result["style"]["display_name"],
                    "personality": validation_result["personality"]["display_name"],
                },
                "test_user_info": {
                    "qiao_id": user_match_result["test_user"]["qiao_id"],
                    "username": user_match_result["test_user"]["username"],
                    "nickname": user_match_result["test_user_profile"]["nickname"],
                },
                "relationship_scores": validation_result["relationship_scores"],
                "available_llm_configs": validation_result["llm_configs"],
            }

        except (ValidationError, UserMatcherError) as e:
            return {
                "ready": False,
                "error_code": e.error_code,
                "error_message": e.message,
                "suggestions": getattr(e, "suggestions", []),
            }

        except Exception as e:
            logger.error("test_readiness_check_error", character_id=character_id, error=str(e))
            return {
                "ready": False,
                "error_code": "SYSTEM_ERROR",
                "error_message": f"System error during readiness check: {str(e)}",
                "suggestions": ["Check system logs", "Contact administrator"],
            }


# Global instance for dependency injection
ai_character_chat_test_service = AICharacterChatTestService()

# Export main service and exceptions for easy import
__all__ = [
    "AICharacterChatTestService",
    "AICharacterChatTestError",
    "ai_character_chat_test_service",
]

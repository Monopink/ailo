"""
AI Character Chat Test Executor Service

Handles test execution by directly calling the main conversation logic.
Manages test session logging and result formatting while maintaining
complete reuse of the core business logic.
"""

import time
from typing import Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.ai.conversation_flow import process_conversation
from services.ai.data import save_context_entry
from services.ai.data.mutations import finalize_context_if_locked
from enums import AIContextRole, AIAggregateState
from models.ai.character import AICharacter
from models.ai.log import AIRequestLog
from models.user import User
from utils.logging import get_logger

logger = get_logger(__name__)


class ExecutorError(Exception):
    """Exception raised when test execution fails"""

    def __init__(self, message: str, error_code: str = "EXECUTOR_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class ExecutorService:
    """Stateless service for AI character chat test execution"""

    async def execute_character_chat_test(
        self,
        db: AsyncSession,
        character_qiao_id: str,
        user_qiao_id: str,
        llm_config_name: str,
        test_message: str,
        request_overrides: dict | None = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute AI character chat test by calling main conversation logic.

        This method ensures 100% reuse of the main business logic by directly
        calling process_conversation() while managing test-specific logging.

        Test mode: Returns all messages immediately (no delay).
        No test_session_id - uses conversation_id for tracking.

        Args:
            db: Database session
            character_qiao_id: Character's qiao_id
            user_qiao_id: Test user's qiao_id
            llm_config_name: LLM configuration name
            test_message: Test message content

        Returns:
            Test result with conversation data and performance metrics

        Raises:
            ExecutorError: If test execution fails
        """
        log_id = None

        try:
            # Query character and user IDs
            character_result = await db.execute(
                select(AICharacter.id, AICharacter.style_id, AICharacter.personality_id).where(
                    AICharacter.qiao_id == character_qiao_id
                )
            )
            character = character_result.one()

            user_result = await db.execute(select(User.id).where(User.qiao_id == user_qiao_id))
            user_id = user_result.scalar_one()

            # Create test request log
            log_entry = AIRequestLog(
                character_id=character.id,
                user_id=user_id,
                style_id=character.style_id,
                personality_id=character.personality_id,
                request_type="test",
                request={"message": test_message, "config_name": llm_config_name},
                status=1,  # pending
            )
            db.add(log_entry)
            await db.flush()  # Get the ID
            log_id = log_entry.id

            logger.info(
                "ai_character_test_started",
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
                log_id=log_id,
            )

            # Optionally create a LOCKED user context to follow buffer/state machine behavior
            locked_context_id = None
            if persist:
                try:
                    context_data = {
                        "character_qiao_id": character_qiao_id,
                        "user_qiao_id": user_qiao_id,
                        "role": AIContextRole.USER,
                        "content": test_message,
                        "aggregate_state": AIAggregateState.LOCKED,
                    }
                    locked_context_id = await save_context_entry(db, context_data)
                    if locked_context_id:
                        logger.debug(
                            "test_user_context_locked",
                            character_qiao_id=character_qiao_id,
                            user_qiao_id=user_qiao_id,
                            context_id=locked_context_id,
                        )
                    else:
                        logger.warning(
                            "test_user_context_save_failed",
                            character_qiao_id=character_qiao_id,
                            user_qiao_id=user_qiao_id,
                        )
                except Exception as e:
                    logger.error(
                        "test_user_context_lock_error",
                        error=str(e),
                        character_qiao_id=character_qiao_id,
                        user_qiao_id=user_qiao_id,
                    )

            # Execute main conversation logic - 100% reuse，传入 locked_context_id 以复用完整业务路径
            start_time = time.time()

            conversation_result = await process_conversation(
                db=db,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                message_content=test_message,
                config_name=llm_config_name,
                request_overrides=request_overrides,
                locked_context_id=locked_context_id,
                persist=persist,
            )

            end_time = time.time()
            response_time_ms = int((end_time - start_time) * 1000)

            # Update test request log with complete request payload
            request_payload = conversation_result.get("request_payload")
            if request_payload:
                # Store complete API request payload for debugging
                log_entry.request = request_payload
            else:
                # Fallback to basic info if payload not available
                log_entry.request = {
                    "message": test_message,
                    "config_name": llm_config_name,
                    "error": "request_payload not available",
                }

            # Store response without request_payload to avoid data duplication
            log_entry.response = {
                "success": conversation_result.get("success"),
                "context_id": conversation_result.get("context_id"),
                "response": conversation_result.get("response"),
                "usage": conversation_result.get("usage"),
                "model": conversation_result.get("model"),
                "config_used": conversation_result.get("config_used"),
            }
            log_entry.status = 1  # success
            log_entry.response_time = response_time_ms
            log_entry.token_count = conversation_result.get("usage", {}).get("total_tokens", 0)
            log_entry.provider_name = conversation_result.get("config_used", {}).get("provider_name")
            log_entry.model_name = conversation_result.get("config_used", {}).get("model")
            log_entry.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Extract AI response from conversation result
            ai_response = conversation_result.get("response", {})

            # Test mode: Merge all messages
            all_messages = ai_response.get("outgoing_messages", []) + ai_response.get(
                "followup_messages", []
            )

            # Format test result
            result = {
                "success": True,
                "test_mode": "immediate",
                "conversation": {
                    "all_messages": all_messages,
                    "outgoing_messages": ai_response.get("outgoing_messages", []),
                    "followup_messages": ai_response.get("followup_messages", []),
                    "should_reply": ai_response.get("should_reply", False),
                    "attack_detected": ai_response.get("attack_detected", False),
                    "internal_thoughts": ai_response.get("internal_thoughts", ""),
                    "score_updates": ai_response.get("score", {}),
                    "memory_operations": ai_response.get("memory_operations", []),
                },
                "performance": {
                    "response_time_ms": response_time_ms,
                    "llm_tokens": conversation_result.get("usage", {}).get("total_tokens", 0),
                },
                "request_payload": conversation_result.get("request_payload"),
                "log_id": log_id,
            }

            # Finalize user context window to COMPLETE when persist enabled
            if persist and locked_context_id:
                try:
                    updated = await finalize_context_if_locked(db, locked_context_id)
                    logger.debug(
                        "test_user_context_finalize",
                        context_id=locked_context_id,
                        updated=updated,
                    )
                except Exception as e:
                    logger.error(
                        "test_user_context_finalize_failed",
                        error=str(e),
                        context_id=locked_context_id,
                    )

            logger.info(
                "ai_character_test_completed",
                character_qiao_id=character_qiao_id,
                response_time_ms=response_time_ms,
                messages_count=len(all_messages),
            )

            return result

        except Exception as e:
            # Handle errors and update request log
            if log_id:
                try:
                    log_entry.response = {"error": str(e)}
                    log_entry.status = 2  # failed
                    log_entry.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                except Exception:
                    pass  # Don't fail on logging error

            logger.error(
                "ai_character_test_failed",
                character_qiao_id=character_qiao_id,
                error=str(e),
                exc_info=True,
            )

            raise ExecutorError(f"Test execution failed: {str(e)}", error_code="EXECUTION_FAILED")


# Global instance for dependency injection
executor_service = ExecutorService()

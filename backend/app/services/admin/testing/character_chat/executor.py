"""
AI Character Chat Test Executor Service

Handles test execution by directly calling the main conversation logic.
Manages test session logging and result formatting while maintaining
complete reuse of the core business logic.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from enums import MessageType
from models.ai.character import AICharacter
from models.ai.log import AIRequestLog
from models.user import User
from services.ai.conversation_flow import process_conversation
from services.message.processing.buffer import (
    add_message_to_buffer,
    finalize_buffer_if_locked,
    force_lock_latest_window,
)
from services.message.schemas import InboundMessageEvent
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
        persist: bool = False,
        contact_conv_id: Optional[str] = None,
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

            locked_buffer_id: Optional[int] = None
            user_message_item_id: Optional[int] = None
            if persist:
                if not contact_conv_id:
                    raise ExecutorError(
                        "Contact conversation_id is required when persist=True",
                        error_code="CONTACT_REQUIRED",
                    )
                locked_buffer_id, user_message_item_id = await self._seed_test_user_context(
                    db=db,
                    user_qiao_id=user_qiao_id,
                    character_qiao_id=character_qiao_id,
                    conv_id=contact_conv_id,
                    test_message=test_message,
                )

            # Execute main conversation logic - 100% reuse，传入 locked_buffer_id 以复用完整业务路径
            start_time = time.time()

            conversation_result = await process_conversation(
                db=db,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                message_content=test_message,
                config_name=llm_config_name,
                request_overrides=request_overrides,
                locked_buffer_id=locked_buffer_id,
                user_message_item_id=user_message_item_id,
                message_blocks=None,
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

            history_messages, current_user_message = _extract_history_messages(
                request_payload,
                fallback_message=test_message,
            )

            # Store response without request_payload to avoid data duplication
            log_entry.response = {
                "success": conversation_result.get("success"),
                "buffer_id": conversation_result.get("buffer_id"),
                "assistant_item_id": conversation_result.get("assistant_item_id"),
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

            # Test mode: Merge all messages with newlines between them
            outgoing = ai_response.get("outgoing_messages", [])
            followup = ai_response.get("followup_messages", [])
            all_messages = outgoing + followup

            # Format test result
            result = {
                "success": True,
                "test_mode": "immediate",
                "buffer_id": conversation_result.get("buffer_id"),
                "assistant_item_id": conversation_result.get("assistant_item_id"),
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
                "history_messages": history_messages,
                "current_user_message": current_user_message,
                "response_body": ai_response,
                "log_id": log_id,
            }

            # Finalize user context window to COMPLETE when persist enabled
            if persist and locked_buffer_id:
                try:
                    updated = await finalize_buffer_if_locked(db, locked_buffer_id)
                    await db.commit()
                    logger.debug(
                        "test_user_context_finalize",
                        buffer_id=locked_buffer_id,
                        updated=updated,
                    )
                except Exception as e:
                    logger.error(
                        "test_user_context_finalize_failed",
                        error=str(e),
                        buffer_id=locked_buffer_id,
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

    async def _seed_test_user_context(
        self,
        *,
        db: AsyncSession,
        user_qiao_id: str,
        character_qiao_id: str,
        conv_id: str,
        test_message: str,
    ) -> Tuple[int, int]:
        """
        Buffer the admin test message and lock the latest window immediately.
        """
        if not test_message or not test_message.strip():
            raise ExecutorError(
                "Test message cannot be empty",
                error_code="EMPTY_TEST_MESSAGE",
            )
        now_ms = int(time.time() * 1000)
        msg_token = f"admin_test_{now_ms}"
        event = InboundMessageEvent(
            conversation_id=conv_id,
            from_qiao_id=user_qiao_id,
            to_qiao_id=character_qiao_id,
            content=test_message,
            message_type=MessageType.TEXT,
            sent_at_ms=now_ms,
            msg_id_client=msg_token,
            msg_id_provider_inbound=f"{msg_token}_provider",
            supports_typing=False,
        )

        await add_message_to_buffer(db, event, character_qiao_id)
        locked_window = await force_lock_latest_window(db, user_qiao_id, character_qiao_id)
        if not locked_window:
            raise ExecutorError(
                "Unable to lock buffered user context for testing",
                error_code="CONTEXT_LOCK_FAILED",
            )

        logger.debug(
            "test_user_context_locked",
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
            buffer_id=locked_window.buffer_id,
            conversation_item_id=locked_window.conversation_item_id,
        )

        return locked_window.buffer_id, locked_window.conversation_item_id


# Global instance for dependency injection
executor_service = ExecutorService()


def _extract_history_messages(
    request_payload: Optional[Dict[str, Any]],
    fallback_message: str,
) -> Tuple[List[Dict[str, str]], str]:
    messages = _coerce_payload_messages(request_payload)
    normalized: List[Dict[str, str]] = []

    for message in messages:
        role = str(message.get("role") or "user")
        text = _flatten_message_content(message.get("content"))
        if not text:
            fallback_text = message.get("text_content") or message.get("text")
            if isinstance(fallback_text, str):
                text = fallback_text
        normalized.append({"role": role, "text": text})

    last_user_idx: Optional[int] = None
    for index, item in enumerate(normalized):
        if item["role"] == "user":
            last_user_idx = index

    current_user_message = fallback_message
    history_slice = normalized
    if last_user_idx is not None:
        candidate = normalized[last_user_idx]["text"].strip()
        if candidate:
            current_user_message = candidate
        history_slice = normalized[:last_user_idx]

    history_messages = [item for item in history_slice if item["role"] in ("user", "assistant")]
    return history_messages, current_user_message


def _coerce_payload_messages(request_payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(request_payload, dict):
        return []

    if isinstance(request_payload.get("input"), list):
        return [msg for msg in request_payload["input"] if isinstance(msg, dict)]

    if isinstance(request_payload.get("messages"), list):
        return [msg for msg in request_payload["messages"] if isinstance(msg, dict)]

    nested = request_payload.get("payload")
    if isinstance(nested, dict) and isinstance(nested.get("messages"), list):
        return [msg for msg in nested["messages"] if isinstance(msg, dict)]

    return []


def _flatten_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
        return "".join(parts)

    if content is None:
        return ""

    return str(content)

"""
AI Instance Chat Test Executor Service

Handles test execution by directly calling the main conversation logic.
Manages test session logging and result formatting while maintaining
complete reuse of the core business logic.
"""

import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MessageType
from app.models.ai.instance import AIInstance
from app.models.ai.log import AIRequestLog
from app.models.user import User
from app.services.ai.orchestrators.conversation_flow import process_conversation
from app.services.message.processing.buffer import (
    add_message_to_buffer,
    finalize_buffer_if_locked,
    force_lock_latest_window,
)
from app.services.message.schemas import InboundMessageEvent
from app.type_defs import JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ExecutorError(Exception):
    """Exception raised when test execution fails"""

    def __init__(self, message: str, error_code: str = "EXECUTOR_ERROR") -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class ExecutorService:
    """Stateless service for AI instance chat test execution"""

    async def execute_instance_chat_test(
        self,
        db: AsyncSession,
        instance_qiao_id: str,
        user_qiao_id: str,
        llm_config_name: str,
        test_message: str,
        request_overrides: dict[str, Any] | None = None,
        persist: bool = False,
        contact_conv_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute AI instance chat test by calling main conversation logic.

        This method ensures 100% reuse of the main business logic by directly
        calling process_conversation() while managing test-specific logging.

        Test mode: Returns all messages immediately (no delay).
        No test_session_id - uses conversation_id for tracking.

        Args:
            db: Database session
            instance_qiao_id: Instance's qiao_id
            user_qiao_id: Test user's qiao_id
            llm_config_name: LLM configuration name
            test_message: Test message content

        Returns:
            Test result with conversation data and performance metrics

        Raises:
            ExecutorError: If test execution fails
        """
        log_id = None
        log_entry: AIRequestLog | None = None

        if persist and not contact_conv_id:
            raise ExecutorError(
                "Contact conversation_id is required when persist=True",
                error_code="CONTACT_REQUIRED",
            )

        try:
            instance, user_id = await self._load_instance_and_user(
                db=db,
                instance_qiao_id=instance_qiao_id,
                user_qiao_id=user_qiao_id,
            )

            log_entry = await self._create_test_request_log(
                db=db,
                instance=instance,
                user_id=user_id,
                user_qiao_id=user_qiao_id,
                test_message=test_message,
                llm_config_name=llm_config_name,
            )
            log_id = log_entry.id

            logger.info(
                "ai_instance_test_started",
                instance_qiao_id=instance_qiao_id,
                user_qiao_id=user_qiao_id,
                log_id=log_id,
            )

            locked_buffer_id: int | None = None
            user_message_item_id: int | None = None
            if persist:
                # contact_conv_id is guaranteed to be str here due to earlier validation
                assert contact_conv_id is not None
                locked_buffer_id, user_message_item_id = await self._seed_test_user_context(
                    db=db,
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    conv_id=contact_conv_id,
                    test_message=test_message,
                )

            # Execute main conversation logic with locked_buffer_id to reuse full flow
            start_time = time.time()

            conversation_result = await process_conversation(
                db=db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
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

            request_payload = conversation_result.get("request_payload")
            # Type narrowing: request_payload can be JSONValue, narrow to dict or None
            request_payload_dict: dict[str, Any] | None = (
                request_payload if isinstance(request_payload, dict) else None
            )
            history_messages, current_user_message = _extract_history_messages(
                request_payload_dict,
                fallback_message=test_message,
            )

            self._update_log_entry(
                log_entry=log_entry,
                conversation_result=conversation_result,
                test_message=test_message,
                llm_config_name=llm_config_name,
                response_time_ms=response_time_ms,
                request_payload=request_payload_dict,
            )
            await db.commit()

            result, all_messages = self._build_test_result(
                conversation_result=conversation_result,
                response_time_ms=response_time_ms,
                history_messages=history_messages,
                current_user_message=current_user_message,
                log_id=log_id,
            )

            # Finalize user context window to COMPLETE when persist enabled
            if persist and locked_buffer_id:
                await self._finalize_persisted_context(db, locked_buffer_id)

            logger.info(
                "ai_instance_test_completed",
                instance_qiao_id=instance_qiao_id,
                response_time_ms=response_time_ms,
                messages_count=len(all_messages),
            )

        except Exception as e:
            # Handle errors and update request log
            if log_id:
                try:
                    log_entry.response = {"error": str(e)}
                    log_entry.status = 2  # failed
                    log_entry.completed_at = datetime.now(UTC)
                    await db.commit()
                except Exception as log_exc:
                    logger.warning(
                        "ai_instance_test_log_update_failed",
                        error=str(log_exc),
                        log_id=log_id,
                    )

            logger.error(
                "ai_instance_test_failed",
                instance_qiao_id=instance_qiao_id,
                error=str(e),
                exc_info=True,
            )

            raise ExecutorError(
                f"Test execution failed: {e!s}", error_code="EXECUTION_FAILED"
            ) from e
        else:
            return result

    async def _load_instance_and_user(
        self,
        *,
        db: AsyncSession,
        instance_qiao_id: str,
        user_qiao_id: str,
    ) -> tuple[Any, int]:
        """Fetch instance row (id/style/personality) and target user id."""

        instance_result = await db.execute(
            select(AIInstance.id, AIInstance.style_id, AIInstance.personality_id).where(
                AIInstance.qiao_id == instance_qiao_id
            )
        )
        instance = instance_result.one()

        user_result = await db.execute(select(User.id).where(User.qiao_id == user_qiao_id))
        user_id = user_result.scalar_one()
        return instance, user_id

    async def _create_test_request_log(
        self,
        *,
        db: AsyncSession,
        instance: Any,
        user_id: int,
        user_qiao_id: str,
        test_message: str,
        llm_config_name: str,
    ) -> AIRequestLog:
        """Persist a pending AIRequestLog row for the test run."""

        log_entry = AIRequestLog(
            instance_id=instance.id,
            user_id=user_id,
            user_qiao_id=user_qiao_id,
            style_id=instance.style_id,
            personality_id=instance.personality_id,
            request_type="test",
            request={"message": test_message, "config_name": llm_config_name},
            status=1,  # pending
        )
        db.add(log_entry)
        await db.flush()
        return log_entry

    def _update_log_entry(
        self,
        *,
        log_entry: AIRequestLog,
        conversation_result: JSONDict,
        test_message: str,
        llm_config_name: str,
        response_time_ms: int,
        request_payload: JSONDict | None,
    ) -> None:
        """Fill in request/response metadata for the AIRequestLog."""

        if request_payload:
            log_entry.request = request_payload
        else:
            log_entry.request = {
                "message": test_message,
                "config_name": llm_config_name,
                "error": "request_payload not available",
            }

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
        usage_dict = conversation_result.get("usage", {})
        config_used_dict = conversation_result.get("config_used", {})

        # Extract and convert values with proper type handling
        total_tokens_val = usage_dict.get("total_tokens", 0) if isinstance(usage_dict, dict) else 0
        log_entry.token_count = (
            int(total_tokens_val) if isinstance(total_tokens_val, int | float) else 0
        )

        provider_name_val = (
            config_used_dict.get("provider_name") if isinstance(config_used_dict, dict) else None
        )
        log_entry.provider_name = str(provider_name_val) if provider_name_val is not None else None

        model_name_val = (
            config_used_dict.get("model") if isinstance(config_used_dict, dict) else None
        )
        log_entry.model_name = str(model_name_val) if model_name_val is not None else None
        log_entry.completed_at = datetime.now(UTC)

    def _build_test_result(
        self,
        *,
        conversation_result: JSONDict,
        response_time_ms: int,
        history_messages: list[dict[str, str]],
        current_user_message: str,
        log_id: int | None,
    ) -> tuple[JSONDict, list[Any]]:
        """Summarize conversation result for admin response."""

        ai_response = conversation_result.get("response", {})
        outgoing_val = (
            ai_response.get("outgoing_messages", []) if isinstance(ai_response, dict) else []
        )
        followup_val = (
            ai_response.get("followup_messages", []) if isinstance(ai_response, dict) else []
        )

        # Ensure they are lists for unpacking
        outgoing: list[Any] = outgoing_val if isinstance(outgoing_val, list) else []
        followup: list[Any] = followup_val if isinstance(followup_val, list) else []
        all_messages: list[Any] = [*outgoing, *followup]
        result: JSONDict = {
            "success": True,
            "test_mode": "immediate",
            "buffer_id": conversation_result.get("buffer_id"),
            "assistant_item_id": conversation_result.get("assistant_item_id"),
            "conversation": {
                "all_messages": all_messages,
                "outgoing_messages": outgoing,
                "followup_messages": followup,
                "should_reply": ai_response.get("should_reply", False),
                "attack_detected": ai_response.get("attack_detected", False),
                "internal_thoughts": ai_response.get("internal_thoughts", ""),
                "score_updates": ai_response.get("score", {}),
                "memory_operations": _normalize_memory_operations(
                    ai_response.get("memory_operations")
                ),
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
        return result, all_messages

    async def _finalize_persisted_context(self, db: AsyncSession, locked_buffer_id: int) -> None:
        """Finalize persisted buffer and keep errors isolated."""

        try:
            updated = await finalize_buffer_if_locked(db, locked_buffer_id)
            await db.commit()
            logger.debug(
                "test_user_context_finalize",
                buffer_id=locked_buffer_id,
                updated=updated,
            )
        except Exception as exc:
            logger.error(
                "test_user_context_finalize_failed",
                error=str(exc),
                buffer_id=locked_buffer_id,
            )

    async def _seed_test_user_context(
        self,
        *,
        db: AsyncSession,
        user_qiao_id: str,
        instance_qiao_id: str,
        conv_id: str,
        test_message: str,
    ) -> tuple[int, int]:
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
            to_qiao_id=instance_qiao_id,
            content=test_message,
            message_type=MessageType.TEXT,
            sent_at_ms=now_ms,
            msg_id_client=msg_token,
            msg_id_provider_inbound=f"{msg_token}_provider",
            supports_typing=False,
        )

        await add_message_to_buffer(db, event, instance_qiao_id)
        locked_window = await force_lock_latest_window(db, user_qiao_id, instance_qiao_id)
        if not locked_window:
            raise ExecutorError(
                "Unable to lock buffered user context for testing",
                error_code="CONTEXT_LOCK_FAILED",
            )

        logger.debug(
            "test_user_context_locked",
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
            buffer_id=locked_window.buffer_id,
            conversation_item_id=locked_window.conversation_item_id,
        )

        return locked_window.buffer_id, locked_window.conversation_item_id


# Global instance for dependency injection
executor_service = ExecutorService()


def _extract_history_messages(
    request_payload: dict[str, Any] | None,
    fallback_message: str,
) -> tuple[list[dict[str, str]], str]:
    messages = _coerce_payload_messages(request_payload)
    normalized: list[dict[str, str]] = []

    for message in messages:
        role = str(message.get("role") or "user")
        text = _flatten_message_content(message.get("content"))
        if not text:
            fallback_text = message.get("text_content") or message.get("text")
            if isinstance(fallback_text, str):
                text = fallback_text
        normalized.append({"role": role, "text": text})

    last_user_idx: int | None = None
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


def _coerce_payload_messages(request_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
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
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
        return "".join(parts)

    if content is None:
        return ""

    return str(content)


def _normalize_memory_operations(value: Any) -> JSONDict:
    normalized: JSONDict = {"remove": [], "update": [], "refresh": [], "add": []}
    if not isinstance(value, dict):
        return normalized

    remove_items = value.get("remove")
    if isinstance(remove_items, list):
        normalized["remove"] = [item for item in remove_items if isinstance(item, str) and item]

    update_items = value.get("update")
    if isinstance(update_items, list):
        updates: list[JSONDict] = []
        for item in update_items:
            if not isinstance(item, dict):
                continue
            old_content = item.get("old_content")
            new_content = item.get("new_content")
            if not isinstance(old_content, str) or not isinstance(new_content, str):
                continue
            entry: JSONDict = {"old_content": old_content, "new_content": new_content}
            new_importance = item.get("new_importance")
            if isinstance(new_importance, int | float):
                entry["new_importance"] = int(new_importance)
            updates.append(entry)
        normalized["update"] = updates  # type: ignore[assignment]

    refresh_items = value.get("refresh")
    if isinstance(refresh_items, list):
        normalized["refresh"] = [item for item in refresh_items if isinstance(item, str) and item]

    add_items = value.get("add")
    if isinstance(add_items, list):
        additions: list[JSONDict] = []
        for item in add_items:
            if not isinstance(item, dict):
                continue
            memory_type = item.get("memory_type")
            content = item.get("content")
            importance = item.get("importance")
            if memory_type not in {"core", "recent"}:
                continue
            if not isinstance(content, str) or not content:
                continue
            if not isinstance(importance, int | float):
                continue
            additions.append(
                {
                    "memory_type": memory_type,
                    "content": content,
                    "importance": int(importance),
                }
            )
        normalized["add"] = additions  # type: ignore[assignment]

    return normalized

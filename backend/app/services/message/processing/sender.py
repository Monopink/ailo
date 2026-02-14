"""
Async AI message sending with typing simulation and turn-version preemption checks.
"""

from __future__ import annotations

import asyncio
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.crud.contact import contact as contact_crud
from app.enums import AIMessageBufferState, MessageType
from app.models.ai import AIConversationState
from app.services.ai.queries.updates import create_conversation_item
from app.services.message.outbound.sender import (
    fanout_realtime_typing_best_effort,
    send_timeline_message,
)
from app.services.message.processing.buffer import finalize_buffer_if_locked
from app.services.message.processing.runtime import is_active_turn
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

logger = get_logger(__name__)

_TURN_CHECK_INTERVAL_SECONDS = 0.2


@dataclass
class SendExecutionResult:
    """Message sending outcome summary for post-send orchestration."""

    first_message_sent: bool
    completed: bool
    interrupted: bool


async def clear_conversation_pending_messages(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
) -> None:
    """Clear pending outgoing messages for one conversation."""

    await _clear_pending_messages(db, user_qiao_id, instance_qiao_id)


async def send_ai_messages_with_typing(
    session_factory: async_sessionmaker[AsyncSession],
    user_qiao_id: str,
    instance_qiao_id: str,
    buffer_id: int | None,
    outgoing_messages: list[str],
    followup_messages: list[str],
    typing_speed_seconds_per_word: float,
    followup_delay_seconds: float,
    llm_request_id: int | None,
    task_turn_version: int,
) -> SendExecutionResult:
    """
    Send AI messages sequentially while simulating typing latency.
    """

    if not outgoing_messages and not followup_messages:
        async with session_factory() as db:
            await _clear_pending_messages(db, user_qiao_id, instance_qiao_id)
            if buffer_id is not None:
                await finalize_buffer_if_locked(
                    db,
                    buffer_id,
                    target_state=AIMessageBufferState.COMPLETE,
                )
            await db.commit()
        logger.info(
            "sending_task_skipped_empty_payload",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            task_turn_version=task_turn_version,
        )
        return SendExecutionResult(
            first_message_sent=False,
            completed=True,
            interrupted=False,
        )

    first_message_sent = False

    async with session_factory() as db:
        try:
            outgoing_sent, interrupted, first_message_sent = await _send_message_list(
                db=db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                buffer_id=buffer_id,
                messages=outgoing_messages,
                typing_speed=typing_speed_seconds_per_word,
                llm_request_id=llm_request_id,
                task_turn_version=task_turn_version,
                first_message_sent=first_message_sent,
            )
            if interrupted:
                await _cancel_buffer_before_first_message(
                    db,
                    buffer_id=buffer_id,
                    first_message_sent=first_message_sent,
                )
                await _save_pending_messages(
                    db,
                    user_qiao_id,
                    instance_qiao_id,
                    outgoing_messages[outgoing_sent:],
                )
                await db.commit()
                logger.info(
                    "sending_interrupted_during_outgoing",
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    task_turn_version=task_turn_version,
                    sent_count=outgoing_sent,
                )
                return SendExecutionResult(
                    first_message_sent=first_message_sent,
                    completed=False,
                    interrupted=True,
                )

            if followup_messages:
                interrupted = await _wait_for_turn_change(
                    db=db,
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    task_turn_version=task_turn_version,
                    duration_seconds=followup_delay_seconds,
                )
                if interrupted:
                    await _cancel_buffer_before_first_message(
                        db,
                        buffer_id=buffer_id,
                        first_message_sent=first_message_sent,
                    )
                    await _clear_pending_messages(db, user_qiao_id, instance_qiao_id)
                    await db.commit()
                    logger.info(
                        "sending_interrupted_during_followup_delay",
                        user_qiao_id=user_qiao_id,
                        instance_qiao_id=instance_qiao_id,
                        task_turn_version=task_turn_version,
                    )
                    return SendExecutionResult(
                        first_message_sent=first_message_sent,
                        completed=False,
                        interrupted=True,
                    )

                followup_sent, interrupted, first_message_sent = await _send_message_list(
                    db=db,
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    buffer_id=buffer_id,
                    messages=followup_messages,
                    typing_speed=typing_speed_seconds_per_word,
                    llm_request_id=llm_request_id,
                    task_turn_version=task_turn_version,
                    first_message_sent=first_message_sent,
                )
                if interrupted:
                    await _cancel_buffer_before_first_message(
                        db,
                        buffer_id=buffer_id,
                        first_message_sent=first_message_sent,
                    )
                    await _clear_pending_messages(db, user_qiao_id, instance_qiao_id)
                    await db.commit()
                    logger.info(
                        "sending_interrupted_during_followup",
                        user_qiao_id=user_qiao_id,
                        instance_qiao_id=instance_qiao_id,
                        task_turn_version=task_turn_version,
                        sent_count=followup_sent,
                    )
                    return SendExecutionResult(
                        first_message_sent=first_message_sent,
                        completed=False,
                        interrupted=True,
                    )

            await _clear_pending_messages(db, user_qiao_id, instance_qiao_id)
            await db.commit()
            logger.info(
                "all_messages_sent_successfully",
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                buffer_id=buffer_id,
                task_turn_version=task_turn_version,
            )
            return SendExecutionResult(
                first_message_sent=first_message_sent,
                completed=True,
                interrupted=False,
            )

        except Exception as exc:
            await db.rollback()
            if buffer_id is not None and not first_message_sent:
                try:
                    cancelled = await finalize_buffer_if_locked(
                        db,
                        buffer_id,
                        target_state=AIMessageBufferState.CANCELLED,
                    )
                    if cancelled:
                        await db.commit()
                    else:
                        await db.rollback()
                except Exception:
                    await db.rollback()
                    logger.exception(
                        "sending_cancel_buffer_failed",
                        user_qiao_id=user_qiao_id,
                        instance_qiao_id=instance_qiao_id,
                        buffer_id=buffer_id,
                        task_turn_version=task_turn_version,
                    )
            logger.error(
                "sending_task_failed",
                error=str(exc),
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                task_turn_version=task_turn_version,
            )
            raise


async def _send_message_list(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    instance_qiao_id: str,
    buffer_id: int | None,
    messages: list[str],
    typing_speed: float,
    llm_request_id: int | None,
    task_turn_version: int,
    first_message_sent: bool,
) -> tuple[int, bool, bool]:
    """
    Send messages sequentially and stop when task turn is no longer active.

    Returns:
        (sent_count, interrupted, first_message_sent)
    """
    if not messages:
        return 0, False, first_message_sent

    contact = await contact_crud.get_user_contact(
        db, user_qiao_id=user_qiao_id, contact_qiao_id=instance_qiao_id
    )
    if not contact:
        raise ValueError(
            f"Contact between user {user_qiao_id} and instance {instance_qiao_id} not found"
        )

    conv_id = contact.conversation_id

    for idx, message in enumerate(messages):
        if not await is_active_turn(db, user_qiao_id, instance_qiao_id, task_turn_version):
            return idx, True, first_message_sent

        typing_duration = calculate_typing_time(message, typing_speed)
        if typing_duration > 0:
            await fanout_realtime_typing_best_effort(
                db=db,
                from_qiao_id=instance_qiao_id,
                to_qiao_id=user_qiao_id,
                conv_id=conv_id,
                typing_state="start",
            )
            interrupted = await _wait_for_turn_change(
                db=db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                task_turn_version=task_turn_version,
                duration_seconds=typing_duration,
            )
            if interrupted:
                logger.debug(
                    "interrupted_during_typing",
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    task_turn_version=task_turn_version,
                    position=idx,
                )
                return idx, True, first_message_sent

        if not await is_active_turn(db, user_qiao_id, instance_qiao_id, task_turn_version):
            return idx, True, first_message_sent

        await _send_and_record_message(
            db=db,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            conv_id=conv_id,
            buffer_id=buffer_id,
            message=message,
            llm_request_id=llm_request_id,
        )
        if not first_message_sent:
            if buffer_id is not None:
                finalized = await finalize_buffer_if_locked(
                    db,
                    buffer_id,
                    target_state=AIMessageBufferState.COMPLETE,
                )
                if not finalized:
                    raise ValueError(
                        "Failed to finalize locked buffer after first assistant message."
                    )
            first_message_sent = True
        await db.commit()

    return len(messages), False, first_message_sent


async def _cancel_buffer_before_first_message(
    db: AsyncSession,
    *,
    buffer_id: int | None,
    first_message_sent: bool,
) -> None:
    """Cancel locked buffer when first assistant message was never persisted."""
    if buffer_id is None or first_message_sent:
        return

    cancelled = await finalize_buffer_if_locked(
        db,
        buffer_id,
        target_state=AIMessageBufferState.CANCELLED,
    )
    if not cancelled:
        logger.warning("buffer_cancel_skipped_not_locked", buffer_id=buffer_id)


async def _wait_for_turn_change(
    *,
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
    task_turn_version: int,
    duration_seconds: float,
) -> bool:
    """
    Wait for duration and return True when task turn is preempted.
    """

    remaining = max(duration_seconds, 0.0)
    while remaining > 0:
        if not await is_active_turn(db, user_qiao_id, instance_qiao_id, task_turn_version):
            return True
        sleep_window = min(_TURN_CHECK_INTERVAL_SECONDS, remaining)
        await asyncio.sleep(sleep_window)
        remaining -= sleep_window

    return not await is_active_turn(db, user_qiao_id, instance_qiao_id, task_turn_version)


async def _send_and_record_message(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    instance_qiao_id: str,
    conv_id: str,
    buffer_id: int | None,
    message: str,
    llm_request_id: int | None,
) -> None:
    """
    Persist single assistant timeline message and conversation item.
    """
    msg_id_server = f"msg_{generate_snowflake_id()}"
    await send_timeline_message(
        db=db,
        from_qiao_id=instance_qiao_id,
        to_qiao_id=user_qiao_id,
        conv_id=conv_id,
        content=message,
        message_type=MessageType.TEXT,
        msg_id=msg_id_server,
        llm_request_id=llm_request_id,
    )

    item_id = await create_conversation_item(
        db,
        {
            "instance_qiao_id": instance_qiao_id,
            "user_qiao_id": user_qiao_id,
            "role": "assistant",
            "message_type": "text",
            "text_content": message,
            "buffer_id": buffer_id,
            "created_at": datetime.now(UTC),
        },
    )
    if item_id is None:
        raise ValueError("Assistant conversation item persistence failed.")


async def _save_pending_messages(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
    outgoing_remaining: list[str],
) -> None:
    """
    Persist pending outgoing messages for the conversation.
    """
    total = len(outgoing_remaining)
    if total == 0:
        await _clear_pending_messages(db, user_qiao_id, instance_qiao_id)
        return

    payload: dict[str, Any] = {
        "outgoing": outgoing_remaining,
        "total_pending": total,
    }

    state = await db.get(AIConversationState, (user_qiao_id, instance_qiao_id))
    now = datetime.now(UTC)

    if not state:
        state = AIConversationState(
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            pending_messages=payload,
            interrupted_at=now,
        )
        db.add(state)
    else:
        state.pending_messages = payload
        state.interrupted_at = now


async def _clear_pending_messages(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
) -> None:
    """
    Remove pending messages for the conversation (if any).
    """
    state = await db.get(AIConversationState, (user_qiao_id, instance_qiao_id))
    if state:
        await db.delete(state)


def calculate_typing_time(message: str, typing_speed: float) -> float:
    """
    Calculate typing latency for message using the configured seconds-per-word rate.
    """
    word_count = _count_words(message)
    return max(typing_speed * word_count, 0.0)


def _count_words(text: str) -> int:
    """
    word definition: 1 full-width char = 1 word, 3 half-width chars = 1 word, emoji counts as 1.
    """

    if not text:
        return 1

    words = 0
    half_width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in {"F", "W"} or unicodedata.category(
            char
        ).startswith("So"):
            words += 1
        else:
            half_width += 1

    words += (half_width + 2) // 3
    return max(words, 1)

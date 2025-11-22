"""
Async AI message sending with typing simulation and interruption support.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from crud.contact import contact as contact_crud
from enums import MessageType
from models.ai import AIConversationState
from services.ai.queries.updates import create_conversation_item
from services.message.outbound.sender import send_message
from utils.logging import get_logger

logger = get_logger(__name__)

_active_sending_tasks: Dict[Tuple[str, str], asyncio.Event] = {}


def interrupt_sending_task(user_qiao_id: str, instance_qiao_id: str) -> None:
    """
    Interrupt in-flight sending task for a conversation (single instance only).
    """
    key = (user_qiao_id, instance_qiao_id)
    event = _active_sending_tasks.get(key)
    if event and not event.is_set():
        event.set()
        logger.info(
            "sending_task_interrupted",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
        )


async def send_ai_messages_with_typing(
    session_factory: async_sessionmaker[AsyncSession],
    user_qiao_id: str,
    instance_qiao_id: str,
    buffer_id: Optional[int],
    outgoing_messages: List[str],
    followup_messages: List[str],
    typing_speed_seconds_per_word: float,
    followup_delay_seconds: float,
) -> None:
    """
    Send AI messages sequentially while simulating typing latency and handling interruptions.
    """

    if not outgoing_messages and not followup_messages:
        async with session_factory() as db:
            await _clear_pending_messages(db, user_qiao_id, instance_qiao_id)
            await db.commit()
        logger.info(
            "sending_task_skipped_empty_payload",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
        )
        return

    conversation_key = (user_qiao_id, instance_qiao_id)
    interrupt_event = asyncio.Event()
    _active_sending_tasks[conversation_key] = interrupt_event

    try:
        async with session_factory() as db:
            try:
                success, sent = await _send_message_list(
                    db=db,
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    buffer_id=buffer_id,
                    messages=outgoing_messages,
                    typing_speed=typing_speed_seconds_per_word,
                    interrupt_event=interrupt_event,
                )
                if not success:
                    await _save_pending_messages(
                        db,
                        user_qiao_id,
                        instance_qiao_id,
                        outgoing_messages[sent:],
                        followup_messages,
                    )
                    await db.commit()
                    logger.info(
                        "sending_interrupted_during_outgoing",
                        user_qiao_id=user_qiao_id,
                        instance_qiao_id=instance_qiao_id,
                        sent_count=sent,
                    )
                    return

                if followup_messages:
                    logger.debug(
                        "waiting_before_followup",
                        user_qiao_id=user_qiao_id,
                        instance_qiao_id=instance_qiao_id,
                        delay_seconds=followup_delay_seconds,
                    )
                    try:
                        await asyncio.wait_for(interrupt_event.wait(), timeout=followup_delay_seconds)
                        await _save_pending_messages(
                            db,
                            user_qiao_id,
                            instance_qiao_id,
                            [],
                            followup_messages,
                        )
                        await db.commit()
                        logger.info(
                            "sending_interrupted_during_followup_delay",
                            user_qiao_id=user_qiao_id,
                            instance_qiao_id=instance_qiao_id,
                        )
                        return
                    except asyncio.TimeoutError:
                        # No interruption -> continue with followup messages
                        pass

                    success, followup_sent = await _send_message_list(
                        db=db,
                        user_qiao_id=user_qiao_id,
                        instance_qiao_id=instance_qiao_id,
                        buffer_id=buffer_id,
                        messages=followup_messages,
                        typing_speed=typing_speed_seconds_per_word,
                        interrupt_event=interrupt_event,
                    )
                    if not success:
                        await _save_pending_messages(
                            db,
                            user_qiao_id,
                            instance_qiao_id,
                            [],
                            followup_messages[followup_sent:],
                        )
                        await db.commit()
                        logger.info(
                            "sending_interrupted_during_followup",
                            user_qiao_id=user_qiao_id,
                            instance_qiao_id=instance_qiao_id,
                            sent_count=followup_sent,
                        )
                        return

                await _clear_pending_messages(db, user_qiao_id, instance_qiao_id)
                await db.commit()
                logger.info(
                    "all_messages_sent_successfully",
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    buffer_id=buffer_id,
                )

            except Exception as exc:
                await db.rollback()
                logger.error(
                    "sending_task_failed",
                    error=str(exc),
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                )
                raise

    finally:
        _active_sending_tasks.pop(conversation_key, None)


async def _send_message_list(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    instance_qiao_id: str,
    buffer_id: Optional[int],
    messages: List[str],
    typing_speed: float,
    interrupt_event: asyncio.Event,
) -> Tuple[bool, int]:
    """
    Send messages sequentially while respecting interruption flag.
    Returns (success, sent_count).
    """
    if not messages:
        return True, 0

    for idx, message in enumerate(messages):
        if interrupt_event.is_set():
            return False, idx

        typing_duration = calculate_typing_time(message, typing_speed)
        if typing_duration > 0:
            try:
                await asyncio.wait_for(interrupt_event.wait(), timeout=typing_duration)
                logger.debug(
                    "interrupted_during_typing",
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    position=idx,
                )
                return False, idx
            except asyncio.TimeoutError:
                pass

        if interrupt_event.is_set():
            return False, idx

        await _send_and_record_message(
            db=db,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            buffer_id=buffer_id,
            message=message,
        )

    return True, len(messages)


async def _send_and_record_message(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    instance_qiao_id: str,
    buffer_id: Optional[int],
    message: str,
) -> None:
    """
    Send single message via provider transport and persist conversation item.
    """
    contact = await contact_crud.get_user_contact(
        db, user_qiao_id=user_qiao_id, contact_qiao_id=instance_qiao_id
    )
    if not contact:
        raise ValueError(f"Contact between user {user_qiao_id} and instance {instance_qiao_id} not found")

    await send_message(
        db=db,
        from_qiao_id=instance_qiao_id,
        to_qiao_id=user_qiao_id,
        conv_id=contact.conv_id,
        content=message,
        message_type=MessageType.TEXT,
    )

    await create_conversation_item(
        db,
        {
            "instance_qiao_id": instance_qiao_id,
            "user_qiao_id": user_qiao_id,
            "role": "assistant",
            "message_type": "text",
            "text_content": message,
            "buffer_id": buffer_id,
            "created_at": datetime.now(timezone.utc),
        },
    )

    await db.commit()


async def _save_pending_messages(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
    outgoing_remaining: List[str],
    followup_remaining: List[str],
) -> None:
    """
    Persist pending messages for the conversation.
    """
    total = len(outgoing_remaining) + len(followup_remaining)
    payload: Dict[str, Any] = {
        "outgoing": outgoing_remaining,
        "followup": followup_remaining,
        "total_pending": total,
    }

    state = await db.get(AIConversationState, (user_qiao_id, instance_qiao_id))
    now = datetime.now(timezone.utc)

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
    import unicodedata

    if not text:
        return 1

    words = 0
    half_width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in {"F", "W"}:
            words += 1
        elif unicodedata.category(char).startswith("So"):
            words += 1
        else:
            half_width += 1

    words += (half_width + 2) // 3
    return max(words, 1)

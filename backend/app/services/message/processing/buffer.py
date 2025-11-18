"""
Message buffer service backed by ai_message_buffer + ai_conversation_items.

Implements the dual-timer aggregation window described in docs/development/ai-message-processing.md.
All text content is persisted directly in ai_conversation_items using Responses API block arrays.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from sqlalchemy import Select, and_, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from enums import MessageType
from enums.common import AIMessageBufferState, ConversationRole
from models.ai.character import AIMessageBuffer, AIConversationItem
from services.ai.queries.character_queries import get_character_relationship_config
from services.ai.queries.updates import create_conversation_item
from services.message.processing.sender import interrupt_sending_task
from services.message.schemas import InboundMessageEvent
from services.config import config_service
from utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


class BufferMessageCategory(str, Enum):
    """Categorized message types for buffer state machine."""

    SUPPORTS_TYPING = "CONTENT_TYPING"
    NO_TYPING = "CONTENT_NO_TYPING"
    TYPING_START = "typing_start"
    TYPING_END = "typing_end"


@dataclass
class BufferTimerConfig:
    """Resolved buffer wait durations (milliseconds)."""

    normal_wait_ms: int
    typing_total_wait_ms: int
    typing_end_wait_ms: int
    no_typing_wait_ms: int


@dataclass
class TimerComputationResult:
    """Represents the next buffer timer state."""

    micro_expires_at_ms: Optional[int]
    macro_expires_at_ms: Optional[int]
    buffer_expires_at_ms: Optional[int]
    last_message_category: Optional[str]


@dataclass
class LockedConversationWindow:
    """Snapshot of a locked buffer window."""

    buffer_id: int
    conversation_item_id: int
    user_qiao_id: str
    character_qiao_id: str
    content: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def add_message_to_buffer(
    db: AsyncSession,
    event: InboundMessageEvent,
    character_qiao_id: str,
) -> None:
    """
    Buffer inbound message according to dual-timer rules.

    Args:
        db: Database session
        event: Inbound message payload
        character_qiao_id: Character external ID
    """
    interrupt_sending_task(event.from_qiao_id, character_qiao_id)

    category = _categorize_event(event)
    if category is None:
        logger.debug("buffer_event_ignored", reason="unsupported_category", type=event.message_type)
        return

    buffer_config = await _get_buffer_config(db)
    current_time = await _get_db_now_ms(db)

    buffer_obj, buffer_item = await _get_latest_open_buffer(
        db, event.from_qiao_id, character_qiao_id, for_update=True
    )

    if buffer_obj is None:
        if event.message_type != MessageType.TEXT:
            logger.debug(
                "typing_event_without_open_buffer",
                user_qiao_id=event.from_qiao_id,
                character_qiao_id=character_qiao_id,
                message_type=event.message_type,
            )
            return

        relationship_config = await get_character_relationship_config(db, character_qiao_id)
        needs_wake = False
        if relationship_config:
            needs_wake = await _check_needs_wake(
                db=db,
                user_qiao_id=event.from_qiao_id,
                character_qiao_id=character_qiao_id,
                relationship_config=relationship_config,
                current_time=current_time,
            )

        if relationship_config and needs_wake:
            await _create_wake_buffer(
                db=db,
                user_qiao_id=event.from_qiao_id,
                character_qiao_id=character_qiao_id,
                event=event,
                category=category,
                config=buffer_config,
                relationship_config=relationship_config,
                current_time=current_time,
            )
        else:
            await _create_new_buffer_window(
                db=db,
                user_qiao_id=event.from_qiao_id,
                character_qiao_id=character_qiao_id,
                event=event,
                category=category,
                config=buffer_config,
                current_time=current_time,
            )
    else:
        if buffer_obj.aggregate_state == AIMessageBufferState.WAITING_WAKEUP:
            await _handle_wake_adjustment(
                db=db,
                buffer_obj=buffer_obj,
                buffer_item=buffer_item,
                event=event,
                category=category,
                config=buffer_config,
                current_time=current_time,
            )
        else:
            await _update_buffer_window(
                db=db,
                buffer_obj=buffer_obj,
                buffer_item=buffer_item,
                event=event,
                category=category,
                config=buffer_config,
                current_time=current_time,
            )

    await db.commit()


async def lock_conversation_preemptively(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
) -> Optional[int]:
    """
    Lock the latest expired OPEN buffer window for processing.
    """
    try:
        now_ms = await _get_db_now_ms(db)

        await db.execute(
            update(AIMessageBuffer)
            .where(
                AIMessageBuffer.user_qiao_id == user_qiao_id,
                AIMessageBuffer.character_qiao_id == character_qiao_id,
                AIMessageBuffer.aggregate_state.in_(
                    [AIMessageBufferState.OPEN, AIMessageBufferState.LOCKED]
                ),
            )
            .values(aggregate_state=AIMessageBufferState.CANCELLED)
        )

        result = await db.execute(
            select(AIMessageBuffer)
            .where(
                AIMessageBuffer.user_qiao_id == user_qiao_id,
                AIMessageBuffer.character_qiao_id == character_qiao_id,
                AIMessageBuffer.aggregate_state == AIMessageBufferState.CANCELLED,
                _buffer_expired_clause(now_ms),
            )
            .order_by(AIMessageBuffer.created_at.desc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        buffer_obj = result.scalar_one_or_none()

        if not buffer_obj:
            await db.rollback()
            logger.debug(
                "no_expired_buffer_to_lock",
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
            )
            return None

        buffer_obj.aggregate_state = AIMessageBufferState.LOCKED
        buffer_obj.locked_at = datetime.utcnow()
        buffer_obj.micro_expires_at_ms = None
        buffer_obj.macro_expires_at_ms = None
        await db.flush()
        await db.commit()

        logger.info(
            "buffer_locked",
            buffer_id=buffer_obj.id,
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
        )
        return buffer_obj.id

    except IntegrityError:
        await db.rollback()
        logger.debug(
            "buffer_lock_conflict",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
        )
        return None
    except Exception as exc:
        await db.rollback()
        logger.error(
            "buffer_lock_failed",
            error=str(exc),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            exc_info=True,
        )
        raise


async def is_buffer_cancelled(db: AsyncSession, buffer_id: int) -> bool:
    """
    Streaming cancellation hook. Returns True if buffer is no longer LOCKED.
    """
    locked = await is_buffer_locked(db, buffer_id)
    return not locked


async def is_buffer_locked(db: AsyncSession, buffer_id: int) -> bool:
    """
    Check whether a message buffer is still locked.
    """
    try:
        result = await db.execute(select(AIMessageBuffer).where(AIMessageBuffer.id == buffer_id))
        buffer_obj = result.scalar_one_or_none()
        if not buffer_obj:
            logger.warning("buffer_not_found_for_lock_check", buffer_id=buffer_id)
            return False

        return buffer_obj.aggregate_state == AIMessageBufferState.LOCKED

    except Exception as exc:
        logger.error("buffer_lock_check_failed", error=str(exc), buffer_id=buffer_id)
        return False


async def get_locked_context(
    db: AsyncSession,
    buffer_id: int,
) -> Optional[LockedConversationWindow]:
    """
    Fetch locked buffer snapshot containing aggregated user content.
    """
    try:
        buffer_obj, item_obj = await _get_buffer_and_item(db, buffer_id, require_locked=True)
        if not buffer_obj or not item_obj:
            return None

        content_text = item_obj.text_content or ""
        return LockedConversationWindow(
            buffer_id=buffer_obj.id,
            conversation_item_id=item_obj.id,
            user_qiao_id=buffer_obj.user_qiao_id,
            character_qiao_id=buffer_obj.character_qiao_id,
            content=content_text,
        )

    except Exception as exc:
        logger.error("locked_context_fetch_failed", error=str(exc), buffer_id=buffer_id)
        return None


async def finalize_buffer_if_locked(
    db: AsyncSession,
    buffer_id: int,
    *,
    target_state: AIMessageBufferState = AIMessageBufferState.COMPLETE,
) -> bool:
    """
    Transition a locked buffer to its terminal state (COMPLETE/CANCELLED).
    """
    try:
        result = await db.execute(
            select(AIMessageBuffer).where(
                AIMessageBuffer.id == buffer_id,
                AIMessageBuffer.aggregate_state == AIMessageBufferState.LOCKED,
            )
        )
        buffer_obj = result.scalar_one_or_none()

        if not buffer_obj:
            logger.debug("buffer_not_locked_on_finalize", buffer_id=buffer_id)
            return False

        buffer_obj.aggregate_state = target_state
        await db.flush()

        logger.info(
            "buffer_finalized",
            buffer_id=buffer_id,
            new_state=target_state.name,
        )
        return True

    except Exception as exc:
        logger.error("buffer_finalize_failed", error=str(exc), buffer_id=buffer_id)
        return False


async def reset_open_conversation_windows(db: AsyncSession) -> int:
    """
    Cancel lingering OPEN/LOCKED windows (used on startup).
    """
    result = await db.execute(
        update(AIMessageBuffer)
        .where(
            AIMessageBuffer.aggregate_state.in_(
                [
                    AIMessageBufferState.WAITING_WAKEUP,
                    AIMessageBufferState.OPEN,
                    AIMessageBufferState.LOCKED,
                ]
            )
        )
        .values(
            aggregate_state=AIMessageBufferState.CANCELLED,
            micro_expires_at_ms=None,
            macro_expires_at_ms=None,
            last_message_category=None,
            wake_expires_at_ms=None,
            wake_adjustment_count=0,
        )
    )
    await db.commit()
    cancelled = result.rowcount or 0
    if cancelled:
        logger.info("buffer_windows_reset", cancelled=cancelled)
    return cancelled


# ---------------------------------------------------------------------------
# Internal helpers - wake mechanism
# ---------------------------------------------------------------------------


async def _check_needs_wake(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    relationship_config: Dict[str, Any],
    current_time: int,
) -> bool:
    """Decide if a wake wait is required based on recent conversation activity."""

    wake_window_ms = int(relationship_config.get("wake_window_ms", 0))
    if wake_window_ms <= 0:
        return False

    result = await db.execute(
        select(AIMessageBuffer)
        .where(
            AIMessageBuffer.user_qiao_id == user_qiao_id,
            AIMessageBuffer.character_qiao_id == character_qiao_id,
            AIMessageBuffer.aggregate_state == AIMessageBufferState.COMPLETE,
        )
        .order_by(AIMessageBuffer.created_at.desc())
        .limit(1)
    )
    last_buffer = result.scalar_one_or_none()
    if not last_buffer:
        return False

    last_timestamp = last_buffer.last_msg_time_ms
    if last_timestamp is None and last_buffer.created_at is not None:
        last_timestamp = int(last_buffer.created_at.timestamp() * 1000)
    if last_timestamp is None:
        return False

    elapsed = max(current_time - last_timestamp, 0)
    return elapsed > wake_window_ms


async def _create_wake_buffer(
    *,
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    event: InboundMessageEvent,
    category: BufferMessageCategory,
    config: BufferTimerConfig,
    relationship_config: Dict[str, Any],
    current_time: int,
) -> None:
    """Create a WAITING_WAKEUP buffer that delays aggregation until wake timer expires."""

    wake_min = int(relationship_config.get("wake_time_min_ms", 3000))
    wake_max = int(relationship_config.get("wake_time_max_ms", 3000))
    wake_bias = relationship_config.get("wake_time_bias", "balanced")

    sampled_delay = sample_wake_time(wake_min, wake_max, wake_bias)
    wake_expires_at_ms = current_time + sampled_delay

    timer_state = _compute_timer_state(
        prev_category=None,
        current_category=category,
        current_micro=None,
        current_macro=None,
        now_ms=wake_expires_at_ms,
        config=config,
    )
    buffer_expires_at_ms = timer_state.buffer_expires_at_ms or wake_expires_at_ms

    msg_id_client = event.msg_id_client or event.msg_id_provider_inbound
    client_msg_ids = [msg_id_client] if msg_id_client else []

    buffer_obj = AIMessageBuffer(
        user_qiao_id=user_qiao_id,
        character_qiao_id=character_qiao_id,
        aggregate_state=AIMessageBufferState.WAITING_WAKEUP,
        micro_expires_at_ms=timer_state.micro_expires_at_ms,
        macro_expires_at_ms=timer_state.macro_expires_at_ms,
        buffer_expires_at_ms=buffer_expires_at_ms,
        last_message_category=timer_state.last_message_category,
        first_msg_id_client=msg_id_client,
        last_msg_id_client=msg_id_client,
        message_count=1,
        last_msg_time_ms=current_time,
        wake_expires_at_ms=wake_expires_at_ms,
        wake_adjustment_count=0,
    )
    db.add(buffer_obj)
    await db.flush()

    await create_conversation_item(
        db,
        {
            "user_qiao_id": user_qiao_id,
            "character_qiao_id": character_qiao_id,
            "role": ConversationRole.USER.value,
            "message_type": "text",
            "text_content": event.content or "",
            "buffer_id": buffer_obj.id,
            "client_msg_ids": client_msg_ids,
        },
    )

    logger.info(
        "wake_buffer_created",
        buffer_id=buffer_obj.id,
        user_qiao_id=user_qiao_id,
        character_qiao_id=character_qiao_id,
        wake_duration_ms=sampled_delay,
    )


async def _handle_wake_adjustment(
    *,
    db: AsyncSession,
    buffer_obj: AIMessageBuffer,
    buffer_item: Optional[AIConversationItem],
    event: InboundMessageEvent,
    category: Optional[BufferMessageCategory],
    config: BufferTimerConfig,
    current_time: int,
) -> None:
    """Adjust wake timer and merge message content while still waiting to wake."""

    if event.message_type != MessageType.TEXT:
        logger.debug(
            "wake_buffer_non_text_ignored",
            buffer_id=buffer_obj.id,
            message_type=event.message_type,
        )
        return

    relationship_config = await get_character_relationship_config(db, buffer_obj.character_qiao_id)
    if not relationship_config:
        relationship_config = _default_relationship_timing()

    wake_expires_at_ms = buffer_obj.wake_expires_at_ms or current_time
    remaining_ms = max(wake_expires_at_ms - current_time, 0)
    adjustment_mode = relationship_config.get("wake_time_adjustment", "none")
    min_wake_ms = int(relationship_config.get("wake_time_min_ms", 0))
    adjusted_remaining = adjust_wake_time(remaining_ms, adjustment_mode, min_wake_ms)
    new_wake_expires_at_ms = current_time + adjusted_remaining

    timer_state = _compute_timer_state(
        prev_category=_category_from_value(buffer_obj.last_message_category),
        current_category=category,
        current_micro=buffer_obj.micro_expires_at_ms,
        current_macro=buffer_obj.macro_expires_at_ms,
        now_ms=new_wake_expires_at_ms,
        config=config,
    )
    buffer_expires_at_ms = timer_state.buffer_expires_at_ms or new_wake_expires_at_ms

    msg_id_client = event.msg_id_client or event.msg_id_provider_inbound
    update_values: Dict[str, Any] = {
        "wake_expires_at_ms": new_wake_expires_at_ms,
        "wake_adjustment_count": (buffer_obj.wake_adjustment_count or 0) + 1,
        "micro_expires_at_ms": timer_state.micro_expires_at_ms,
        "macro_expires_at_ms": timer_state.macro_expires_at_ms,
        "buffer_expires_at_ms": buffer_expires_at_ms,
        "last_message_category": timer_state.last_message_category,
        "message_count": buffer_obj.message_count + 1,
        "last_msg_time_ms": current_time,
        "last_msg_id_client": msg_id_client,
    }

    await db.execute(
        update(AIMessageBuffer)
        .where(AIMessageBuffer.id == buffer_obj.id)
        .values(update_values)
    )

    if buffer_item:
        buffer_item.text_content = _append_text(buffer_item.text_content, event.content)
        if msg_id_client:
            client_ids = list(buffer_item.client_msg_ids or [])
            client_ids.append(msg_id_client)
            buffer_item.client_msg_ids = client_ids
    else:
        client_ids = [msg_id_client] if msg_id_client else []
        await create_conversation_item(
            db,
            {
                "user_qiao_id": buffer_obj.user_qiao_id,
                "character_qiao_id": buffer_obj.character_qiao_id,
                "role": ConversationRole.USER.value,
                "message_type": "text",
                "text_content": event.content or "",
                "buffer_id": buffer_obj.id,
                "client_msg_ids": client_ids,
            },
        )

    logger.debug(
        "wake_buffer_adjusted",
        buffer_id=buffer_obj.id,
        new_wake_remaining_ms=adjusted_remaining,
        adjustment_mode=adjustment_mode,
    )


def sample_wake_time(min_ms: int, max_ms: int, bias: str = "balanced") -> int:
    """Sample a wake wait duration based on the configured bias."""

    if min_ms >= max_ms:
        return max(min_ms, max_ms)

    u = random.random()
    ratio = u

    if bias == "centered":
        mean = 0.5
        std = 0.15
        ratio = random.gauss(mean, std)
        ratio = max(0.0, min(1.0, ratio))
    elif bias == "fast":
        ratio = u ** 2
    elif bias == "slow":
        ratio = math.sqrt(u)
    elif bias == "very_fast":
        ratio = u ** 3
    elif bias == "very_slow":
        ratio = u ** (1 / 3)

    return int(min_ms + ratio * (max_ms - min_ms))


def adjust_wake_time(current_remaining_ms: int, adjustment_mode: str, wake_time_min_ms: int) -> int:
    """
    Adjust the wake timer when new messages arrive during the waiting window.

    Spec (2025-11-14): only two modes remain.
    - `none`: keep the remaining delay, but never let it drop under 1 second.
    - `random_half`: 50% chance to shrink the timer by a random factor between 2% and 100%.
      The other 50% keeps the timer unchanged. Regardless of the branch, the remaining time
      after adjustment must be at least 1 second (1000 ms).

    The wake_time_min_ms argument is kept for signature compatibility with earlier iterations.
    """

    minimum_ms = 1000  # Absolute floor mandated by the spec (1 second).
    if current_remaining_ms <= 0:
        return minimum_ms

    if adjustment_mode != "random_half":
        return max(current_remaining_ms, minimum_ms)

    random_number = random.randint(1, 100)
    if random_number <= 50:
        # Scale the current wait by (random_number / 50), i.e. 2%-100% of the original.
        adjusted = int(current_remaining_ms * random_number / 50)
    else:
        adjusted = current_remaining_ms

    return max(adjusted, minimum_ms)


def _default_relationship_timing() -> Dict[str, Any]:
    """Provide a sane default configuration if relationship timing is missing."""

    return {
        "wake_time_min_ms": 2000,
        "wake_time_max_ms": 4000,
        "wake_time_bias": "balanced",
        "wake_window_ms": 60000,
        "wake_time_adjustment": "random_half",
        "no_reply_probability": 0.0,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_latest_open_buffer(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    *,
    for_update: bool = False,
) -> Tuple[Optional[AIMessageBuffer], Optional[AIConversationItem]]:
    buffer_query = (
        select(AIMessageBuffer)
        .where(
            AIMessageBuffer.user_qiao_id == user_qiao_id,
            AIMessageBuffer.character_qiao_id == character_qiao_id,
            AIMessageBuffer.aggregate_state.in_(
                [AIMessageBufferState.WAITING_WAKEUP, AIMessageBufferState.OPEN]
            ),
        )
        .order_by(AIMessageBuffer.created_at.desc())
        .limit(1)
    )

    if for_update:
        buffer_query = buffer_query.with_for_update(skip_locked=True)

    buffer_result = await db.execute(buffer_query)
    buffer_obj = buffer_result.scalar_one_or_none()
    if not buffer_obj:
        return None, None

    item_result = await db.execute(
        select(AIConversationItem).where(AIConversationItem.buffer_id == buffer_obj.id)
    )
    item_obj = item_result.scalar_one_or_none()

    return buffer_obj, item_obj


async def _get_buffer_and_item(
    db: AsyncSession,
    buffer_id: int,
    *,
    require_locked: bool = False,
) -> Tuple[Optional[AIMessageBuffer], Optional[AIConversationItem]]:
    query = select(AIMessageBuffer, AIConversationItem).join(
        AIConversationItem,
        AIConversationItem.buffer_id == AIMessageBuffer.id,
    )
    if require_locked:
        query = query.where(
            AIMessageBuffer.id == buffer_id,
            AIMessageBuffer.aggregate_state == AIMessageBufferState.LOCKED,
        )
    else:
        query = query.where(AIMessageBuffer.id == buffer_id)

    result = await db.execute(query)
    row = result.first()
    if not row:
        return None, None
    return row[0], row[1]


async def _create_new_buffer_window(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    event: InboundMessageEvent,
    category: BufferMessageCategory,
    config: BufferTimerConfig,
    current_time: int,
) -> None:
    timer_state = _compute_timer_state(
        prev_category=None,
        current_category=category,
        current_micro=None,
        current_macro=None,
        now_ms=current_time,
        config=config,
    )

    if timer_state.buffer_expires_at_ms is None:
        timer_state.buffer_expires_at_ms = current_time

    msg_id_client = event.msg_id_client or event.msg_id_provider_inbound
    client_msg_ids: List[str] = [msg_id_client] if msg_id_client else []

    buffer_obj = AIMessageBuffer(
        user_qiao_id=user_qiao_id,
        character_qiao_id=character_qiao_id,
        aggregate_state=AIMessageBufferState.OPEN,
        micro_expires_at_ms=timer_state.micro_expires_at_ms,
        macro_expires_at_ms=timer_state.macro_expires_at_ms,
        last_message_category=timer_state.last_message_category,
        first_msg_id_client=msg_id_client,
        last_msg_id_client=msg_id_client,
        message_count=1,
        last_msg_time_ms=current_time,
    )

    db.add(buffer_obj)
    await db.flush()

    await create_conversation_item(
        db,
        {
            "user_qiao_id": user_qiao_id,
            "character_qiao_id": character_qiao_id,
            "role": ConversationRole.USER.value,
            "message_type": "text",
            "text_content": event.content or "",
            "buffer_id": buffer_obj.id,
            "client_msg_ids": client_msg_ids,
        },
    )

    logger.info(
        "buffer_window_created",
        user_qiao_id=user_qiao_id,
        character_qiao_id=character_qiao_id,
        buffer_id=buffer_obj.id,
    )


async def _update_buffer_window(
    db: AsyncSession,
    buffer_obj: AIMessageBuffer,
    buffer_item: Optional[AIConversationItem],
    event: InboundMessageEvent,
    category: BufferMessageCategory,
    config: BufferTimerConfig,
    current_time: int,
) -> None:
    timer_state = _compute_timer_state(
        prev_category=_category_from_value(buffer_obj.last_message_category),
        current_category=category,
        current_micro=buffer_obj.micro_expires_at_ms,
        current_macro=buffer_obj.macro_expires_at_ms,
        now_ms=current_time,
        config=config,
    )

    update_values: Dict[str, Any] = {
        "micro_expires_at_ms": timer_state.micro_expires_at_ms,
        "macro_expires_at_ms": timer_state.macro_expires_at_ms,
        "last_message_category": timer_state.last_message_category,
    }

    if timer_state.buffer_expires_at_ms:
        update_values["buffer_expires_at_ms"] = timer_state.buffer_expires_at_ms

    if event.message_type == MessageType.TEXT:
        update_values["message_count"] = buffer_obj.message_count + 1
        update_values["last_msg_time_ms"] = current_time
        update_values["last_msg_id_client"] = event.msg_id_client or event.msg_id_provider_inbound

    await db.execute(
        update(AIMessageBuffer)
        .where(AIMessageBuffer.id == buffer_obj.id)
        .values(update_values)
    )

    if event.message_type == MessageType.TEXT:
        msg_id_client = event.msg_id_client or event.msg_id_provider_inbound

        if buffer_item:
            buffer_item.text_content = _append_text(buffer_item.text_content, event.content)
            if msg_id_client:
                existing_ids = list(buffer_item.client_msg_ids or [])
                existing_ids.append(msg_id_client)
                buffer_item.client_msg_ids = existing_ids
        else:
            await create_conversation_item(
                db,
                {
                    "user_qiao_id": buffer_obj.user_qiao_id,
                    "character_qiao_id": buffer_obj.character_qiao_id,
                    "role": ConversationRole.USER.value,
                    "message_type": "text",
                    "text_content": event.content or "",
                    "buffer_id": buffer_obj.id,
                    "client_msg_ids": [msg_id_client] if msg_id_client else [],
                },
            )

    logger.info("buffer_window_updated", buffer_id=buffer_obj.id, category=category.name)


def _append_text(existing: Optional[str], addition: str) -> str:
    if not existing:
        return addition or ""
    if not addition:
        return existing
    return f"{existing}\n{addition}"


def _categorize_event(event: InboundMessageEvent) -> Optional[BufferMessageCategory]:
    if event.message_type == MessageType.TEXT:
        return (
            BufferMessageCategory.SUPPORTS_TYPING
            if event.supports_typing
            else BufferMessageCategory.NO_TYPING
        )
    if event.message_type == MessageType.TYPING_START:
        return BufferMessageCategory.TYPING_START
    if event.message_type == MessageType.TYPING_END:
        return BufferMessageCategory.TYPING_END
    return None


def _category_from_value(value: Optional[str]) -> Optional[BufferMessageCategory]:
    if value is None:
        return None
    try:
        return BufferMessageCategory(value)
    except ValueError:
        return None


def _compute_timer_state(
    *,
    prev_category: Optional[BufferMessageCategory],
    current_category: Optional[BufferMessageCategory],
    current_micro: Optional[int],
    current_macro: Optional[int],
    now_ms: int,
    config: BufferTimerConfig,
) -> TimerComputationResult:
    new_micro = current_micro
    new_macro = current_macro
    last_category_value = prev_category.value if prev_category else None

    if current_category is None:
        return TimerComputationResult(
            micro_expires_at_ms=new_micro,
            macro_expires_at_ms=new_macro,
            buffer_expires_at_ms=_compute_buffer_expiration(new_micro, new_macro),
            last_message_category=last_category_value,
        )

    last_category_value = current_category.value

    if current_category == BufferMessageCategory.SUPPORTS_TYPING:
        new_micro = now_ms + config.normal_wait_ms
    elif current_category == BufferMessageCategory.NO_TYPING:
        new_micro = now_ms + config.no_typing_wait_ms
    elif current_category == BufferMessageCategory.TYPING_END:
        new_micro = now_ms + config.typing_end_wait_ms
    elif current_category == BufferMessageCategory.TYPING_START:
        new_micro = None
        new_macro = (
            now_ms + config.typing_total_wait_ms if config.typing_total_wait_ms > 0 else None
        )

    if prev_category == BufferMessageCategory.TYPING_START:
        if current_category in (
            BufferMessageCategory.SUPPORTS_TYPING,
            BufferMessageCategory.TYPING_END,
        ):
            new_macro = None

    if prev_category == BufferMessageCategory.TYPING_END and current_category == BufferMessageCategory.TYPING_START:
        new_micro = None
        new_macro = (
            now_ms + config.typing_total_wait_ms if config.typing_total_wait_ms > 0 else None
        )

    buffer_expires = _compute_buffer_expiration(new_micro, new_macro)

    return TimerComputationResult(
        micro_expires_at_ms=new_micro,
        macro_expires_at_ms=new_macro,
        buffer_expires_at_ms=buffer_expires,
        last_message_category=last_category_value,
    )


def _compute_buffer_expiration(
    micro_expires_at_ms: Optional[int], macro_expires_at_ms: Optional[int]
) -> Optional[int]:
    candidates = [t for t in (micro_expires_at_ms, macro_expires_at_ms) if t is not None]
    return min(candidates) if candidates else None


def _buffer_expired_clause(now_ms: int):
    return or_(
        and_(
            AIMessageBuffer.micro_expires_at_ms.is_not(None),
            AIMessageBuffer.micro_expires_at_ms <= now_ms,
        ),
        and_(
            AIMessageBuffer.macro_expires_at_ms.is_not(None),
            AIMessageBuffer.macro_expires_at_ms <= now_ms,
        ),
    )


async def _get_buffer_config(db: AsyncSession) -> BufferTimerConfig:
    return BufferTimerConfig(
        normal_wait_ms=await config_service.get_int(db, "message_buffer_normal_wait_ms"),
        typing_total_wait_ms=await config_service.get_int(db, "message_buffer_typing_total_wait_ms"),
        typing_end_wait_ms=await config_service.get_int(db, "message_buffer_typing_end_wait_ms"),
        no_typing_wait_ms=await config_service.get_int(db, "message_buffer_no_typing_wait_ms"),
    )


async def _get_db_now_ms(db: AsyncSession) -> int:
    """
    Get current timestamp in milliseconds from database clock.
    """
    try:
        result = await db.execute(text("SELECT (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT"))
        value = result.scalar_one()
        return int(value)
    except Exception as exc:
        logger.warning("db_clock_fallback", error=str(exc))
        return int(time.time() * 1000)

"""
Message buffer service backed by ai_message_buffer + ai_conversation_items.

Implements the dual-timer aggregation window described in docs/development/ai-message-processing.md.
All text content is persisted directly in ai_conversation_items using Responses API block arrays.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from sqlalchemy import Select, and_, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from enums import MessageType
from enums.common import AIMessageBufferState, ConversationRole
from models.ai.character import AIMessageBuffer, AIConversationItem
from services.ai.queries.updates import create_conversation_item
from services.message.schemas import InboundMessageEvent
from services.config import config_service
from utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


class BufferMessageCategory(IntEnum):
    """Categorized message types for buffer state machine."""

    SUPPORTS_TYPING = 1
    NO_TYPING = 2
    TYPING_START = 3
    TYPING_END = 4


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
    last_message_category: Optional[int]


@dataclass
class LockedConversationWindow:
    """Snapshot of a locked buffer window."""

    buffer_id: int
    conversation_item_id: int
    user_qiao_id: str
    character_qiao_id: str
    content: str
    content_blocks: List[Dict[str, Any]]


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

        content_blocks = list(item_obj.content or [])
        content_text = _blocks_to_text(content_blocks)
        return LockedConversationWindow(
            buffer_id=buffer_obj.id,
            conversation_item_id=item_obj.id,
            user_qiao_id=buffer_obj.user_qiao_id,
            character_qiao_id=buffer_obj.character_qiao_id,
            content=content_text,
            content_blocks=content_blocks,
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
        .where(AIMessageBuffer.aggregate_state.in_([AIMessageBufferState.OPEN, AIMessageBufferState.LOCKED]))
        .values(
            aggregate_state=AIMessageBufferState.CANCELLED,
            micro_expires_at_ms=None,
            macro_expires_at_ms=None,
            last_message_category=None,
        )
    )
    await db.commit()
    cancelled = result.rowcount or 0
    if cancelled:
        logger.info("buffer_windows_reset", cancelled=cancelled)
    return cancelled


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
    query: Select = (
        select(AIMessageBuffer, AIConversationItem)
        .join(
            AIConversationItem,
            AIConversationItem.buffer_id == AIMessageBuffer.id,
            isouter=True,
        )
        .where(
            AIMessageBuffer.user_qiao_id == user_qiao_id,
            AIMessageBuffer.character_qiao_id == character_qiao_id,
            AIMessageBuffer.aggregate_state == AIMessageBufferState.OPEN,
        )
        .order_by(AIMessageBuffer.created_at.desc())
        .limit(1)
    )
    if for_update:
        query = query.with_for_update(skip_locked=True)

    result = await db.execute(query)
    row = result.first()
    if not row:
        return None, None
    return row[0], row[1]


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

    content_blocks = _build_user_blocks(event.content)
    preview = _build_preview(content_blocks)

    await create_conversation_item(
        db,
        {
            "user_qiao_id": user_qiao_id,
            "character_qiao_id": character_qiao_id,
            "role": ConversationRole.USER.value,
            "content": content_blocks,
            "content_preview": preview,
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
        content_blocks = list(buffer_item.content if buffer_item and buffer_item.content else [])
        content_blocks.append(_build_input_text_block(event.content))
        preview = _build_preview(content_blocks)

        msg_id_client = event.msg_id_client or event.msg_id_provider_inbound

        if buffer_item:
            buffer_item.content = content_blocks
            buffer_item.content_preview = preview
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
                    "content": content_blocks,
                    "content_preview": preview,
                    "buffer_id": buffer_obj.id,
                    "client_msg_ids": [msg_id_client] if msg_id_client else [],
                },
            )

    logger.info("buffer_window_updated", buffer_id=buffer_obj.id, category=category.name)


def _build_input_text_block(content: str) -> Dict[str, Any]:
    return {"type": "input_text", "text": content}


def _build_user_blocks(content: str) -> List[Dict[str, Any]]:
    return [_build_input_text_block(content)]


def _build_preview(blocks: List[Dict[str, Any]], limit: int = 180) -> str:
    accumulator: List[str] = []
    for block in blocks:
        text_value = block.get("text")
        if text_value:
            accumulator.append(text_value)
        if len(" ".join(accumulator)) >= limit:
            break
    preview = " ".join(accumulator)
    return preview[:limit]


def _blocks_to_text(blocks: List[Dict[str, Any]]) -> str:
    texts = []
    for block in blocks:
        text_value = block.get("text")
        if text_value:
            texts.append(text_value)
    return "\n".join(texts)


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


def _category_from_value(value: Optional[int]) -> Optional[BufferMessageCategory]:
    if value is None:
        return None
    try:
        return BufferMessageCategory(value)
    except ValueError:
        return None


def _category_to_value(category: Optional[BufferMessageCategory]) -> Optional[int]:
    return category.value if category is not None else None


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
    last_category_value = _category_to_value(prev_category)

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

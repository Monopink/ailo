"""
Message buffer service (Database-driven implementation).

Buffers messages to reduce AI calls and improve response quality.
Uses ai_contexts table with state machine for preemptive processing.

Design: Follows ai-message-processing.md specification
- Database-driven (no timer-based scheduling)
- Preemptive locking (new messages cancel old processing)
- Streaming early stop support
- Concurrent-safe via unique partial index
"""

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Optional, Callable, Awaitable
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from models.ai.character import AIContext
from enums import AIContextRole, AIAggregateState, MessageType
from services.ai.queries import save_context_entry
from services.message.schemas import InboundMessageEvent
from services.config import config_service
from utils.logging import get_logger

logger = get_logger(__name__)


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


async def add_message_to_buffer(
    db: AsyncSession,
    event: InboundMessageEvent,
    character_qiao_id: str,
) -> None:
    """
    Add message to buffer (database-driven).

    Logic:
    1. Query latest context for this conversation
    2. If latest is USER role with OPEN state → merge into it
    3. Otherwise → create new USER context with OPEN state
    4. Set buffer_expires_at_ms using DB clock

    Processing is triggered by periodic scanner, not timer.

    Args:
        db: Database session
        event: Standardized inbound message event
        character_qiao_id: Character external ID
    """
    try:
        category = _categorize_event(event)
        if category is None:
            logger.debug(
                "buffer_event_ignored",
                reason="unsupported_category",
                message_type=event.message_type,
            )
            return

        buffer_config = await _get_buffer_config(db)
        current_time = await _get_db_now_ms(db)

        latest_context = await _get_latest_open_user_context(
            db, event.from_qiao_id, character_qiao_id
        )

        if latest_context is None:
            if event.message_type != MessageType.TEXT:
                logger.debug(
                    "typing_event_without_open_context",
                    user_qiao_id=event.from_qiao_id,
                    character_qiao_id=character_qiao_id,
                    message_type=event.message_type,
                )
                return

            await _create_new_context(
                db=db,
                user_qiao_id=event.from_qiao_id,
                character_qiao_id=character_qiao_id,
                event=event,
                category=category,
                config=buffer_config,
                current_time=current_time,
            )
        else:
            await _update_context_with_event(
                db=db,
                context=latest_context,
                event=event,
                category=category,
                config=buffer_config,
                current_time=current_time,
            )

        await db.commit()

        logger.info(
            "buffer_event_applied",
            user_qiao_id=event.from_qiao_id,
            character_qiao_id=character_qiao_id,
            category=category.name,
            merged=latest_context is not None,
        )

    except Exception as e:
        await db.rollback()
        logger.error("add_message_to_buffer_error", error=str(e), exc_info=True)
        raise


async def lock_conversation_preemptively(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
) -> Optional[int]:
    """
    Preemptively lock conversation for processing.

    Transaction steps:
    1. Cancel all old OPEN/LOCKED contexts for this conversation
    2. Find the latest expired OPEN context
    3. Lock it (set to LOCKED state)

    Concurrency safety:
    - Relies on unique partial index: only one LOCKED context per conversation
    - Concurrent attempts will fail with IntegrityError
    - Failed attempts return None (graceful handling)

    Args:
        db: Database session
        user_qiao_id: User external ID
        character_qiao_id: Character external ID

    Returns:
        context_id if successfully locked, None otherwise
    """
    try:
        # Get current DB time
        now_ms = await _get_db_now_ms(db)

        # Step 1: Cancel all old OPEN/LOCKED contexts
        cancel_result = await db.execute(
            update(AIContext)
            .where(
                AIContext.user_qiao_id == user_qiao_id,
                AIContext.character_qiao_id == character_qiao_id,
                AIContext.role == AIContextRole.USER,
                AIContext.aggregate_state.in_([
                    AIAggregateState.OPEN,
                    AIAggregateState.LOCKED
                ])
            )
            .values(aggregate_state=AIAggregateState.CANCELLED)
        )

        cancelled_count = cancel_result.rowcount

        # Step 2: Find latest expired OPEN context
        # Note: We need to query again because we just cancelled all OPEN contexts
        # But we want to lock the one that was OPEN and expired before cancellation
        result = await db.execute(
            select(AIContext)
            .where(
                AIContext.user_qiao_id == user_qiao_id,
                AIContext.character_qiao_id == character_qiao_id,
                AIContext.role == AIContextRole.USER,
                AIContext.aggregate_state == AIAggregateState.CANCELLED,
                AIContext.buffer_expires_at_ms <= now_ms
            )
            .order_by(AIContext.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        context = result.scalar_one_or_none()

        if not context:
            await db.rollback()
            logger.debug(
                "no_expired_context_to_lock",
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                cancelled_count=cancelled_count,
            )
            return None

        # Step 3: Lock the context
        context.aggregate_state = AIAggregateState.LOCKED
        await db.flush()
        await db.commit()

        logger.info(
            "conversation_locked_preemptively",
            context_id=context.id,
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            cancelled_count=cancelled_count,
        )

        return context.id

    except IntegrityError as e:
        # Unique constraint violation - another process locked first
        await db.rollback()
        logger.debug(
            "lock_conflict_detected",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            error=str(e),
        )
        return None
    except Exception as e:
        await db.rollback()
        logger.error(
            "lock_preemptively_error",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            exc_info=True,
        )
        raise


async def check_if_cancelled(
    db: AsyncSession,
    context_id: int
) -> bool:
    """
    Check if context has been cancelled (for streaming early stop).

    Used as preemption_checker callback in streaming LLM calls.
    Checks if the context is still in LOCKED state.

    Args:
        db: Database session
        context_id: Context ID to check

    Returns:
        True if context is no longer LOCKED (cancelled/preempted), False otherwise
    """
    try:
        result = await db.execute(
            select(AIContext.aggregate_state)
            .where(AIContext.id == context_id)
        )
        state = result.scalar_one_or_none()

        if state is None:
            logger.warning("context_not_found_for_cancellation_check", context_id=context_id)
            return True  # Context deleted - stop

        is_cancelled = state != AIAggregateState.LOCKED

        if is_cancelled:
            logger.info(
                "context_cancelled_during_streaming",
                context_id=context_id,
                current_state=state.value if state else None,
            )

        return is_cancelled

    except Exception as e:
        logger.error(
            "check_cancelled_error",
            error=str(e),
            context_id=context_id,
            exc_info=True,
        )
        return True  # Fail-safe: stop on error


async def get_locked_context(
    db: AsyncSession,
    context_id: int
) -> Optional[AIContext]:
    """
    Get locked context by ID.

    Args:
        db: Database session
        context_id: Context ID

    Returns:
        AIContext if found and still LOCKED, None otherwise
    """
    try:
        result = await db.execute(
            select(AIContext)
            .where(
                AIContext.id == context_id,
                AIContext.aggregate_state == AIAggregateState.LOCKED
            )
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error("get_locked_context_error", error=str(e), context_id=context_id, exc_info=True)
        return None


# Helper functions


async def _get_latest_open_user_context(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str
) -> Optional[AIContext]:
    """
    Get latest OPEN USER context for a conversation.

    Only returns contexts that are:
    - USER role
    - OPEN state (can be merged)
    """
    result = await db.execute(
        select(AIContext)
        .where(
            AIContext.user_qiao_id == user_qiao_id,
            AIContext.character_qiao_id == character_qiao_id,
            AIContext.role == AIContextRole.USER,
            AIContext.aggregate_state == AIAggregateState.OPEN,
        )
        .order_by(AIContext.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _update_context_with_event(
    db: AsyncSession,
    context: AIContext,
    event: InboundMessageEvent,
    category: BufferMessageCategory,
    config: BufferTimerConfig,
    current_time: int,
) -> None:
    """Apply inbound event to an existing OPEN context."""
    prev_category = _category_from_value(context.last_message_category)

    timer_state = _compute_timer_state(
        prev_category=prev_category,
        current_category=category,
        current_micro=context.micro_expires_at_ms,
        current_macro=context.macro_expires_at_ms,
        now_ms=current_time,
        config=config,
    )

    if timer_state.buffer_expires_at_ms is None:
        # Failsafe: never leave buffer_expires unset
        timer_state.buffer_expires_at_ms = current_time

    update_values = {
        "micro_expires_at_ms": timer_state.micro_expires_at_ms,
        "macro_expires_at_ms": timer_state.macro_expires_at_ms,
        "buffer_expires_at_ms": timer_state.buffer_expires_at_ms,
        "last_message_category": timer_state.last_message_category,
        "aggregate_state": AIAggregateState.OPEN,
    }

    if event.message_type == MessageType.TEXT:
        new_content = _append_message_content(context.content, event.content)
        msg_id_client = event.msg_id_client or event.msg_id_provider_inbound
        update_values.update(
            content=new_content,
            last_msg_id_client=msg_id_client,
            last_msg_time_ms=current_time,
        )

    await db.execute(
        update(AIContext)
        .where(AIContext.id == context.id)
        .values(update_values)
    )

    logger.info(
        "buffer_context_updated",
        context_id=context.id,
        category=category.name,
    )


async def _create_new_context(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    event: InboundMessageEvent,
    category: BufferMessageCategory,
    config: BufferTimerConfig,
    current_time: int,
) -> None:
    """Create a new OPEN context initialized with timers."""
    if event.message_type != MessageType.TEXT:
        raise ValueError("New buffer contexts must start with a TEXT message")

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
    formatted_content = _format_message_with_timestamp(event.content, current_time)

    context_data = {
        "character_qiao_id": character_qiao_id,
        "user_qiao_id": user_qiao_id,
        "role": AIContextRole.USER,
        "content": formatted_content,
        "first_msg_id_client": msg_id_client,
        "last_msg_id_client": msg_id_client,
        "last_msg_time_ms": current_time,
        "micro_expires_at_ms": timer_state.micro_expires_at_ms,
        "macro_expires_at_ms": timer_state.macro_expires_at_ms,
        "buffer_expires_at_ms": timer_state.buffer_expires_at_ms,
        "last_message_category": timer_state.last_message_category,
        "aggregate_state": AIAggregateState.OPEN,
    }

    await save_context_entry(db, context_data)

    logger.info(
        "new_context_created",
        user_qiao_id=user_qiao_id,
        character_qiao_id=character_qiao_id,
    )


def _append_message_content(existing: str, new_message: str) -> str:
    if not existing:
        return new_message
    return f"{existing}\n{new_message}"


def _format_message_with_timestamp(content: str, current_time: int) -> str:
    timestamp_str = datetime.fromtimestamp(current_time / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp_str}] {content}"


async def _get_buffer_config(db: AsyncSession) -> BufferTimerConfig:
    return BufferTimerConfig(
        normal_wait_ms=await config_service.get_int(db, "message_buffer_normal_wait_ms"),
        typing_total_wait_ms=await config_service.get_int(db, "message_buffer_typing_total_wait_ms"),
        typing_end_wait_ms=await config_service.get_int(db, "message_buffer_typing_end_wait_ms"),
        no_typing_wait_ms=await config_service.get_int(db, "message_buffer_no_typing_wait_ms"),
    )


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


def _compute_buffer_expiration(
    micro_expires_at_ms: Optional[int], macro_expires_at_ms: Optional[int]
) -> Optional[int]:
    candidates = [t for t in (micro_expires_at_ms, macro_expires_at_ms) if t is not None]
    return min(candidates) if candidates else None


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

    # Combination-specific adjustments
    if prev_category == BufferMessageCategory.TYPING_START:
        if current_category in (BufferMessageCategory.SUPPORTS_TYPING, BufferMessageCategory.TYPING_END):
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


async def reset_open_conversation_windows(db: AsyncSession) -> int:
    """
    Cancel any lingering OPEN/LOCKED windows (used on startup to drop timers).
    """
    result = await db.execute(
        update(AIContext)
        .where(
            AIContext.role == AIContextRole.USER,
            AIContext.aggregate_state.in_([AIAggregateState.OPEN, AIAggregateState.LOCKED]),
        )
        .values(
            aggregate_state=AIAggregateState.CANCELLED,
            buffer_expires_at_ms=None,
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


async def _get_db_now_ms(db: AsyncSession) -> int:
    """
    Get current timestamp in milliseconds from database clock.

    Uses database clock for consistency across multiple instances.
    """
    try:
        from sqlalchemy import text

        result = await db.execute(text("SELECT (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT"))
        value = result.scalar_one()
        return int(value)
    except Exception as e:
        # Fallback to application clock to avoid blocking on DB
        import time
        logger.warning("db_clock_fallback", error=str(e))
        return int(time.time() * 1000)

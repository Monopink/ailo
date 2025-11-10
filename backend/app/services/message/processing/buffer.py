"""
Message buffer service.

Buffers messages to reduce AI calls and improve response quality.
Uses ai_contexts table for persistent state management.
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import SessionLocal
from models.ai.character import AIContext
from enums import AIContextRole, AIAggregateState, MessageType
from services.ai.queries import save_context_entry
from services.ai.queries.updates import finalize_context_if_locked
from services.ai.conversation_flow import process_conversation
from services.message.schemas import InboundMessageEvent
from services.config import config_service
from utils.logging import get_logger

logger = get_logger(__name__)

# Global timer management (minimal state)
_timers: Dict[str, asyncio.Task] = {}
_timer_lock: asyncio.Lock = asyncio.Lock()


async def add_message_to_buffer(
    db: AsyncSession,
    event: InboundMessageEvent,
    character_qiao_id: str,
) -> None:
    """
    Add message to buffer.

    Logic:
    1. Query latest context for this conversation
    2. If latest is USER role → merge into it
    3. If latest is ASSISTANT role → create new USER context
    4. Schedule/reschedule timer

    Args:
        db: Database session
        user_qiao_id: User external ID
        character_qiao_id: Character external ID
        message_content: Message content
        event: Standardized inbound message event
    """
    try:
        # 1. Get latest context
        latest_context = await _get_latest_context(db, event.from_qiao_id, character_qiao_id)

        # 2. Calculate wait time and use DB clock
        wait_time_ms = await _get_wait_time(db, event)
        current_time = await _get_db_now_ms(db)
        expires_at = current_time + wait_time_ms

        # 3. Determine if we should merge or create new
        if latest_context and latest_context.role == AIContextRole.USER:
            # Merge into existing context
            await _merge_message_into_context(
                db=db,
                context=latest_context,
                message_content=event.content,
                msg_id_client=event.msg_id_client or event.msg_id_provider_inbound,
                expires_at=expires_at,
                current_time=current_time,
            )
        else:
            # Create new context
            await _create_new_context(
                db=db,
                user_qiao_id=event.from_qiao_id,
                character_qiao_id=character_qiao_id,
                message_content=event.content,
                msg_id_client=event.msg_id_client or event.msg_id_provider_inbound,
                expires_at=expires_at,
                current_time=current_time,
            )

        # 4. Schedule timer
        await _schedule_buffer_processing(event.from_qiao_id, character_qiao_id, wait_time_ms)

        logger.info(
            "message_added_to_buffer",
            user_qiao_id=event.from_qiao_id,
            character_qiao_id=character_qiao_id,
            wait_time_ms=wait_time_ms,
        )

    except Exception as e:
        logger.error("add_message_to_buffer_error", error=str(e), exc_info=True)
        raise


async def process_buffered_messages(db: AsyncSession, user_qiao_id: str, character_qiao_id: str) -> None:
    """
    Process buffered messages.

    Logic:
    1. Get latest USER context
    2. If aggregate_state is OPEN → process it
    3. Update aggregate_state to LOCKED
    4. Call AI
    5. Update aggregate_state to COMPLETE
    """
    try:
        # 1. Get latest context
        latest_context = await _get_latest_context(db, user_qiao_id, character_qiao_id)

        if not latest_context:
            logger.warning("no_context_to_process")
            return

        if latest_context.role != AIContextRole.USER:
            logger.warning("latest_context_not_user_role", role=latest_context.role)
            return

        if latest_context.aggregate_state != AIAggregateState.OPEN:
            logger.warning("context_not_open", aggregate_state=latest_context.aggregate_state)
            return

        # 2. Update to LOCKED
        await db.execute(
            update(AIContext)
            .where(AIContext.id == latest_context.id)
            .values(aggregate_state=AIAggregateState.LOCKED)
        )
        await db.commit()

        logger.info(
            "processing_buffered_messages",
            context_id=latest_context.id,
        )

        # 3. Call AI
        await process_conversation(
            db=db,
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            message_content=latest_context.content,
            message_type="text",
            locked_context_id=latest_context.id,
        )

        # 4. Finalize to COMPLETE only if still LOCKED
        await finalize_context_if_locked(db, latest_context.id)

        logger.info("buffered_messages_processed", context_id=latest_context.id)

    except Exception as e:
        logger.error("buffer_processing_error", error=str(e), exc_info=True)
        # Keep status as LOCKED for manual intervention
        raise


# Helper functions


async def _get_latest_context(
    db: AsyncSession, user_qiao_id: str, character_qiao_id: str
) -> Optional[AIContext]:
    """Get latest context for a conversation."""
    result = await db.execute(
        select(AIContext)
        .where(
            AIContext.user_qiao_id == user_qiao_id,
            AIContext.character_qiao_id == character_qiao_id,
        )
        .order_by(AIContext.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    # Compatibility with AsyncMock in tests (may return awaitable)
    try:
        import inspect

        if inspect.isawaitable(row):
            row = await row
    except Exception:
        pass
    return row


async def _merge_message_into_context(
    db: AsyncSession,
    context: AIContext,
    message_content: str,
    msg_id_client: Optional[str],
    expires_at: int,
    current_time: int,
) -> None:
    """
    Merge message into existing context.

    Logic:
    1. Append message content (without timestamp)
    2. Update last_msg_id_client, last_msg_time_ms, buffer_expires_at_ms
    3. Keep aggregate_state as OPEN
    """
    # Append content (no timestamp for subsequent messages)
    new_content = f"{context.content}\n{message_content}"

    # Update fields
    await db.execute(
        update(AIContext)
        .where(AIContext.id == context.id)
        .values(
            content=new_content,
            last_msg_id_client=msg_id_client,
            last_msg_time_ms=current_time,
            buffer_expires_at_ms=expires_at,
            aggregate_state=AIAggregateState.OPEN,
        )
    )
    await db.flush()

    logger.info("message_merged_into_context", context_id=context.id)


async def _create_new_context(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    message_content: str,
    msg_id_client: Optional[str],
    expires_at: int,
    current_time: int,
) -> None:
    """
    Create new context with timestamp.

    Logic:
    1. Format content with timestamp
    2. Create context record with new fields
    """
    # Format content with timestamp
    timestamp_str = datetime.fromtimestamp(current_time / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
    formatted_content = f"[{timestamp_str}] {message_content}"

    # Create context
    context_data = {
        "character_qiao_id": character_qiao_id,
        "user_qiao_id": user_qiao_id,
        "role": AIContextRole.USER,
        "content": formatted_content,
        "first_msg_id_client": msg_id_client,
        "last_msg_id_client": msg_id_client,
        "last_msg_time_ms": current_time,
        "buffer_expires_at_ms": expires_at,
        "aggregate_state": AIAggregateState.OPEN,
    }

    await save_context_entry(db, context_data)

    logger.info("new_context_created", user_qiao_id=user_qiao_id, character_qiao_id=character_qiao_id)


async def _get_wait_time(db: AsyncSession, event: InboundMessageEvent) -> int:
    """Get buffer wait time based on message metadata."""
    if not event.supports_typing:
        return await config_service.get_int(db, "message_buffer_no_typing_wait")

    if event.message_type == MessageType.TYPING_START:
        return await config_service.get_int(db, "message_buffer_typing_wait")
    if event.message_type == MessageType.TYPING_END:
        return await config_service.get_int(db, "message_buffer_typing_end_wait")
    return await config_service.get_int(db, "message_buffer_normal_wait")


async def _schedule_buffer_processing(user_qiao_id: str, character_qiao_id: str, wait_time_ms: int) -> None:
    """
    Schedule buffer processing.

    Logic:
    1. Cancel existing timer for this conversation
    2. Create new timer
    """
    key = f"{user_qiao_id}:{character_qiao_id}"

    async with _timer_lock:
        # Cancel existing timer
        if key in _timers and not _timers[key].done():
            _timers[key].cancel()
            logger.debug("timer_cancelled", key=key)

        # Create new timer
        _timers[key] = asyncio.create_task(_wait_and_process(user_qiao_id, character_qiao_id, wait_time_ms))

        logger.info("timer_scheduled", key=key, wait_time_ms=wait_time_ms)


async def _wait_and_process(user_qiao_id: str, character_qiao_id: str, wait_time_ms: int) -> None:
    """Wait for specified time then process buffer."""
    try:
        await asyncio.sleep(wait_time_ms / 1000.0)
        async with SessionLocal() as session:
            await process_buffered_messages(session, user_qiao_id, character_qiao_id)
    except asyncio.CancelledError:
        logger.debug("timer_cancelled_during_wait")
    except Exception as e:
        logger.error("timer_processing_error", error=str(e), exc_info=True)


async def _get_db_now_ms(db: AsyncSession) -> int:
    """Get current timestamp in milliseconds from database clock."""
    try:
        from sqlalchemy import text

        result = await db.execute(text("SELECT (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT"))
        value = result.scalar_one()
        import inspect

        if inspect.isawaitable(value):
            value = await value
        return int(value)
    except Exception:
        # Fallback to application clock to avoid blocking on DB
        import time

        return int(time.time() * 1000)

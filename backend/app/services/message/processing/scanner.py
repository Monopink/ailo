"""
Periodic scanner for expired buffer contexts.

Scans database every 100ms for expired OPEN contexts and triggers processing.
This replaces the timer-based approach with a database-driven design.

Design: Follows ai-message-processing.md specification
- Scans every 100ms for expired contexts
- Uses preemptive locking for concurrent safety
- Triggers AI processing asynchronously
"""

import asyncio
import random

from core.database import get_sessionmaker
from enums.common import AIMessageBufferState
from models.ai.instance import AIMessageBuffer
from services.ai.orchestrators.conversation_flow import process_conversation
from services.ai.queries.instance_queries import get_instance_relationship_config
from services.message.processing.buffer import (
    _get_db_now_ms,
    finalize_buffer_if_locked,
    get_locked_context,
    lock_conversation_preemptively,
)
from sqlalchemy import and_, or_, select, update
from utils.logging import get_logger

logger = get_logger(__name__)

# Scanner state
_scanner_task: asyncio.Task | None = None
_scanner_running: bool = False
_scan_interval: float = 0.1  # 100ms
_processing_tasks: set[asyncio.Task] = set()
_max_concurrent_processing = 10
_processing_semaphore = asyncio.Semaphore(_max_concurrent_processing)


async def start_buffer_scanner() -> None:
    """
    Start the buffer scanner background task.

    Should be called once during application startup.
    Scans database every 100ms for expired OPEN contexts.
    """
    global _scanner_task, _scanner_running

    if _scanner_running:
        logger.warning("scanner_already_running")
        return

    _scanner_running = True
    _scanner_task = asyncio.create_task(_scanner_loop())
    logger.info("buffer_scanner_started", scan_interval_ms=_scan_interval * 1000)


async def stop_buffer_scanner() -> None:
    """
    Stop the buffer scanner (for graceful shutdown).

    Cancels the background task and waits for it to finish.
    """
    global _scanner_task, _scanner_running

    if not _scanner_running:
        return

    _scanner_running = False
    if _scanner_task and not _scanner_task.done():
        _scanner_task.cancel()
        try:
            await _scanner_task
        except asyncio.CancelledError:
            pass
    _scanner_task = None

    if _processing_tasks:
        await asyncio.gather(*_processing_tasks, return_exceptions=True)
        _processing_tasks.clear()

    logger.info("buffer_scanner_stopped")


async def _scanner_loop() -> None:
    """
    Main scanner loop.

    Runs every 100ms to scan for expired contexts.
    Continues running even if individual scans fail.
    """
    while _scanner_running:
        try:
            await _scan_and_process()
            await asyncio.sleep(_scan_interval)
        except asyncio.CancelledError:
            logger.info("scanner_loop_cancelled")
            break
        except Exception as e:
            logger.error("scanner_loop_error", error=str(e), exc_info=True)
            await asyncio.sleep(_scan_interval)  # Continue despite errors


async def _scan_and_process() -> None:
    """
    Scan for expired contexts and trigger processing.

    Steps:
    1. Promote WAITING_WAKEUP buffers whose wake timers expired
    2. Query expired OPEN contexts (buffer_expires_at_ms <= now)
    3. Group by conversation (user_qiao_id, instance_qiao_id)
    4. For each conversation, attempt preemptive lock
    5. If locked successfully, trigger AI processing asynchronously
    """
    session_factory = get_sessionmaker()
    async with session_factory() as db:
        try:
            # Get current DB time
            now_ms = await _get_db_now_ms(db)

            # Step 1: promote wake-complete buffers
            wake_result = await db.execute(
                update(AIMessageBuffer)
                .where(
                    AIMessageBuffer.aggregate_state == AIMessageBufferState.WAITING_WAKEUP,
                    AIMessageBuffer.wake_expires_at_ms.is_not(None),
                    AIMessageBuffer.wake_expires_at_ms <= now_ms,
                )
                .values(
                    aggregate_state=AIMessageBufferState.OPEN,
                    wake_expires_at_ms=None,
                )
                .execution_options(synchronize_session=False)
            )
            wake_count = wake_result.rowcount or 0
            if wake_count:
                await db.commit()
                logger.info("wake_expired_buffers_transitioned", count=wake_count)

            # Query expired OPEN contexts (distinct conversations)
            result = await db.execute(
                select(
                    AIMessageBuffer.user_qiao_id,
                    AIMessageBuffer.instance_qiao_id,
                )
                .where(
                    AIMessageBuffer.aggregate_state == AIMessageBufferState.OPEN,
                    or_(
                        and_(
                            AIMessageBuffer.micro_expires_at_ms.is_not(None),
                            AIMessageBuffer.micro_expires_at_ms <= now_ms,
                        ),
                        and_(
                            AIMessageBuffer.macro_expires_at_ms.is_not(None),
                            AIMessageBuffer.macro_expires_at_ms <= now_ms,
                        ),
                    ),
                )
                .distinct()
            )

            conversations = result.all()

            if not conversations:
                return  # No expired contexts

            logger.debug(
                "found_expired_contexts",
                count=len(conversations),
                now_ms=now_ms,
            )

            # Process each conversation asynchronously without blocking the scanner loop
            for user_qiao_id, instance_qiao_id in conversations:
                _schedule_processing_task(user_qiao_id, instance_qiao_id)

        except Exception as e:
            logger.error("scan_and_process_error", error=str(e), exc_info=True)


async def _process_conversation_async(
    user_qiao_id: str,
    instance_qiao_id: str,
) -> None:
    """
    Process a single conversation asynchronously.

    Steps:
    1. Attempt preemptive lock (cancel old + lock new)
    2. If successful, get locked context content
    3. Trigger AI processing with buffer_id
    4. Handle errors gracefully (don't crash scanner)

    Args:
        user_qiao_id: User external ID
        instance_qiao_id: Instance external ID
    """
    try:
        session_factory = get_sessionmaker()
        async with session_factory() as db:
            # Step 1: Attempt preemptive lock
            buffer_id = await lock_conversation_preemptively(
                db=db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
            )

            if not buffer_id:
                # Lock failed (conflict or no expired context)
                logger.debug(
                    "lock_failed_for_conversation",
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                )
                return

            # Step 2: Get locked context content
            context = await get_locked_context(db, buffer_id)

            if not context:
                logger.warning(
                    "locked_context_not_found",
                    buffer_id=buffer_id,
                )
                return

            relationship_config = await get_instance_relationship_config(db, instance_qiao_id)
            no_reply_prob = float((relationship_config or {}).get("no_reply_probability", 0.0))
            should_reply = random.random() >= no_reply_prob

            if not should_reply:
                finalized = await finalize_buffer_if_locked(
                    db, buffer_id, target_state=AIMessageBufferState.COMPLETE
                )
                if finalized:
                    await db.commit()
                    logger.info(
                        "buffer_no_reply_decision",
                        buffer_id=buffer_id,
                        no_reply_probability=no_reply_prob,
                    )
                return

            logger.info(
                "triggering_ai_processing",
                buffer_id=buffer_id,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
            )

            # Step 3: Trigger AI processing
            # Note: process_conversation will handle finalization and error handling
            await process_conversation(
                db=db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                message_content=context.content,
                message_type="text",
                locked_buffer_id=buffer_id,
                user_message_item_id=context.conversation_item_id,
                message_blocks=None,
                persist=True,
            )

            logger.info(
                "ai_processing_completed",
                buffer_id=buffer_id,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
            )

    except Exception as e:
        logger.error(
            "process_conversation_async_error",
            error=str(e),
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            exc_info=True,
        )
        # Don't re-raise - let scanner continue with other conversations


def _schedule_processing_task(user_qiao_id: str, instance_qiao_id: str) -> None:
    """
    Schedule conversation processing in background with concurrency limits.
    """

    async def _runner() -> None:
        async with _processing_semaphore:
            await _process_conversation_async(user_qiao_id, instance_qiao_id)

    task = asyncio.create_task(_runner())
    _processing_tasks.add(task)

    def _cleanup(finished: asyncio.Task) -> None:
        _processing_tasks.discard(finished)
        try:
            exc = finished.exception()
        except asyncio.CancelledError:
            exc = None

        if exc:
            logger.error(
                "processing_task_failed",
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                error=str(exc),
            )

    task.add_done_callback(_cleanup)

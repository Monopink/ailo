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
from typing import Optional, Set

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import SessionLocal
from enums.common import AIMessageBufferState
from models.ai.character import AIMessageBuffer
from services.message.processing.buffer import (
    get_locked_context,
    lock_conversation_preemptively,
    _get_db_now_ms,
)
from services.ai.conversation_flow import process_conversation
from utils.logging import get_logger

logger = get_logger(__name__)

# Scanner state
_scanner_task: Optional[asyncio.Task] = None
_scanner_running: bool = False
_scan_interval: float = 0.1  # 100ms
_processing_tasks: Set[asyncio.Task] = set()
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
    1. Query expired OPEN contexts (buffer_expires_at_ms <= now)
    2. Group by conversation (user_qiao_id, character_qiao_id)
    3. For each conversation, attempt preemptive lock
    4. If locked successfully, trigger AI processing asynchronously
    """
    async with SessionLocal() as db:
        try:
            # Get current DB time
            now_ms = await _get_db_now_ms(db)

            # Query expired OPEN contexts (distinct conversations)
            result = await db.execute(
                select(
                    AIMessageBuffer.user_qiao_id,
                    AIMessageBuffer.character_qiao_id,
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
            for user_qiao_id, character_qiao_id in conversations:
                _schedule_processing_task(user_qiao_id, character_qiao_id)

        except Exception as e:
            logger.error("scan_and_process_error", error=str(e), exc_info=True)


async def _process_conversation_async(
    user_qiao_id: str,
    character_qiao_id: str,
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
        character_qiao_id: Character external ID
    """
    try:
        async with SessionLocal() as db:
            # Step 1: Attempt preemptive lock
            buffer_id = await lock_conversation_preemptively(
                db=db,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
            )

            if not buffer_id:
                # Lock failed (conflict or no expired context)
                logger.debug(
                    "lock_failed_for_conversation",
                    user_qiao_id=user_qiao_id,
                    character_qiao_id=character_qiao_id,
                )
                return

            logger.info(
                "triggering_ai_processing",
                buffer_id=buffer_id,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
            )

            # Step 2: Get locked context content
            context = await get_locked_context(db, buffer_id)

            if not context:
                logger.warning(
                    "locked_context_not_found",
                    buffer_id=buffer_id,
                )
                return

            # Step 3: Trigger AI processing
            # Note: process_conversation will handle finalization and error handling
            await process_conversation(
                db=db,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                message_content=context.content,
                message_type="text",
                locked_buffer_id=buffer_id,
                user_message_item_id=context.conversation_item_id,
                message_blocks=context.content_blocks,
                persist=True,
            )

            logger.info(
                "ai_processing_completed",
                buffer_id=buffer_id,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
            )

    except Exception as e:
        logger.error(
            "process_conversation_async_error",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            exc_info=True,
        )
        # Don't re-raise - let scanner continue with other conversations


def _schedule_processing_task(user_qiao_id: str, character_qiao_id: str) -> None:
    """
    Schedule conversation processing in background with concurrency limits.
    """

    async def _runner() -> None:
        async with _processing_semaphore:
            await _process_conversation_async(user_qiao_id, character_qiao_id)

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
                character_qiao_id=character_qiao_id,
                error=str(exc),
            )

    task.add_done_callback(_cleanup)

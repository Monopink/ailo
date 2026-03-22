"""
Periodic scanner for expired buffer contexts.

Scans database every 100ms for expired active contexts and triggers processing.
This replaces the timer-based approach with a database-driven design.

Design: Follows docs/spec/message/buffer.md specification
- Scans every 100ms for expired contexts
- Uses preemptive locking for concurrent safety
- Triggers AI processing asynchronously
"""

import asyncio
import random
from decimal import Decimal

from sqlalchemy import select

from app.core.database import get_sessionmaker
from app.enums.common import AIMessageBufferState
from app.models.ai.instance import AIMessageBuffer
from app.services.ai.orchestrators.conversation_flow import process_conversation
from app.services.ai.queries.instance_queries import get_instance_relationship_config
from app.services.message.processing.buffer import (
    _get_db_now_ms,
    finalize_buffer_if_locked,
    get_locked_context,
    lock_conversation_preemptively,
)
from app.services.message.processing.sender import clear_conversation_pending_messages
from app.utils.logging import get_logger

logger = get_logger(__name__)


# Scanner state
class _ScannerState:
    """Track background scanner status."""

    def __init__(self) -> None:
        self.task: asyncio.Task[None] | None = None
        self.running: bool = False


_scanner_state = _ScannerState()
_scan_interval: float = 0.1  # 100ms
_processing_tasks: set[asyncio.Task[None]] = set()
_max_concurrent_processing = 10
_processing_semaphore = asyncio.Semaphore(_max_concurrent_processing)


async def start_buffer_scanner() -> None:
    """
    Start the buffer scanner background task.

    Should be called once during application startup.
    Scans database every 100ms for expired active contexts.
    """
    if _scanner_state.running:
        logger.warning("scanner_already_running")
        return

    _scanner_state.running = True
    _scanner_state.task = asyncio.create_task(_scanner_loop())
    logger.info("buffer_scanner_started", scan_interval_ms=_scan_interval * 1000)


async def stop_buffer_scanner() -> None:
    """
    Stop the buffer scanner (for graceful shutdown).

    Cancels the background task and waits for it to finish.
    """
    if not _scanner_state.running:
        return

    _scanner_state.running = False
    if _scanner_state.task and not _scanner_state.task.done():
        _scanner_state.task.cancel()
        try:
            await _scanner_state.task
        except asyncio.CancelledError:
            pass
    _scanner_state.task = None

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
    while _scanner_state.running:
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
    1. Query expired active contexts (buffer_expires_at_ms <= now)
    2. Group by conversation (user_qiao_id, instance_qiao_id)
    3. For each conversation, attempt preemptive lock
    4. If locked successfully, trigger AI processing asynchronously
    """
    session_factory = get_sessionmaker()
    async with session_factory() as db:
        try:
            # Get current DB time
            now_ms = await _get_db_now_ms(db)

            # Query expired active contexts (distinct conversations)
            result = await db.execute(
                select(
                    AIMessageBuffer.user_qiao_id,
                    AIMessageBuffer.instance_qiao_id,
                )
                .where(
                    AIMessageBuffer.aggregate_state.in_(
                        [AIMessageBufferState.WAITING_WAKEUP, AIMessageBufferState.OPEN]
                    ),
                    AIMessageBuffer.buffer_expires_at_ms.is_not(None),
                    AIMessageBuffer.buffer_expires_at_ms <= now_ms,
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
    1. Attempt preemptive lock (lock newest expired active window, then apply preemption)
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
            lock_result = await lock_conversation_preemptively(
                db=db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
            )

            if lock_result is None:
                # Lock failed (conflict or no expired context)
                logger.debug(
                    "lock_failed_for_conversation",
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                )
                return
            buffer_id = lock_result.buffer_id
            task_turn_version = lock_result.task_turn_version

            # Step 2: Get locked context content
            context = await get_locked_context(db, buffer_id)

            if not context:
                logger.warning(
                    "locked_context_not_found",
                    buffer_id=buffer_id,
                )
                return

            relationship_config = await get_instance_relationship_config(
                db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
            )
            if relationship_config is None:
                raise ValueError(
                    "Missing relationship config for no_reply_probability; "
                    "relationship_id must be initialized during instance creation"
                )

            no_reply_prob_value = relationship_config.get("no_reply_probability")
            if not isinstance(no_reply_prob_value, int | float | Decimal):
                raise TypeError(
                    f"Invalid no_reply_probability type: {type(no_reply_prob_value).__name__}"
                )
            no_reply_prob = float(no_reply_prob_value)
            should_reply = random.random() >= no_reply_prob

            if not should_reply:
                finalized = await finalize_buffer_if_locked(
                    db, buffer_id, target_state=AIMessageBufferState.COMPLETE
                )
                if finalized:
                    await clear_conversation_pending_messages(db, user_qiao_id, instance_qiao_id)
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
            conversation_result = await process_conversation(
                db=db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                message_content=context.content,
                message_type="text",
                locked_buffer_id=buffer_id,
                user_message_item_id=context.conversation_item_id,
                message_blocks=None,
                persist=True,
                task_turn_version=task_turn_version,
            )

            if bool(conversation_result.get("rejected")):
                logger.info(
                    "ai_processing_business_rejected",
                    buffer_id=buffer_id,
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    reason=conversation_result.get("reason"),
                    error_code=conversation_result.get("error_code"),
                )
                return

            if bool(conversation_result.get("preempted")):
                logger.info(
                    "ai_processing_preempted",
                    buffer_id=buffer_id,
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                )
                return

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


def _schedule_processing_task(user_qiao_id: str, instance_qiao_id: str) -> None:
    """
    Schedule conversation processing in background with concurrency limits.
    """

    async def _runner() -> None:
        async with _processing_semaphore:
            await _process_conversation_async(user_qiao_id, instance_qiao_id)

    task = asyncio.create_task(_runner())
    _processing_tasks.add(task)

    def _cleanup(finished: asyncio.Task[None]) -> None:
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

"""
Background worker to process AI contact requests.

MVP design: a single async loop periodically scans for pending AI contact
requests, locks a small batch (FOR UPDATE SKIP LOCKED), and processes them
sequentially using the same business logic as synchronous path.

This keeps API requests fast (enqueue only) and moves creation work out of
the request path for stability.
"""

import asyncio
from datetime import UTC, datetime

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_sessionmaker
from app.crud.contact import contact_request as contact_request_crud
from app.enums import ContactRequestStatus, ContactType
from app.models.contact import ContactRequest
from app.services.contact.request_service import _process_ai_contact_request
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def _lock_pending_requests(db: AsyncSession, batch_size: int) -> list[ContactRequest]:
    """
    Lock a batch of pending AI contact requests and mark them as PROCESSING.

    Uses SELECT ... FOR UPDATE SKIP LOCKED to avoid contention, then immediately
    marks as PROCESSING and commits to release the lock while preventing other
    workers from picking up the same requests.

    Only processes non-expired requests.
    """

    stmt = (
        select(ContactRequest)
        .where(
            ContactRequest.status == ContactRequestStatus.PENDING,
            ContactRequest.to_type == ContactType.AI,
            ContactRequest.failure_code.is_(None),
            ContactRequest.expires_at > datetime.now(UTC),  # Filter expired requests
        )
        .with_for_update(skip_locked=True)
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    requests = list(result.scalars().all())

    # Immediately mark as PROCESSING to prevent duplicate processing
    if requests:
        for req in requests:
            req.status = ContactRequestStatus.PROCESSING
        await db.commit()

        # Refresh to get updated state
        for req in requests:
            await db.refresh(req)

    return requests


async def _process_one(db: AsyncSession, req: ContactRequest) -> None:
    """
    Process a single contact request using request_service logic.

    The request is already marked as PROCESSING. After processing:
    - ACCEPTED: AI accepted and contact created
    - IGNORED: Business validation failed (template unavailable, etc.)
    - FAILED: System error occurred
    - PROCESSING: AI didn't explicitly accept (fallback to IGNORED)
    """
    try:
        # Cache primitive values to avoid expired attributes later
        user_qiao_id = req.from_qiao_id
        user_id = req.from_id

        await _process_ai_contact_request(
            db=db,
            user_qiao_id=user_qiao_id,
            user_id=user_id,
            contact_request=req,
            alias=None,
            tags=None,
        )

        updated_req = await contact_request_crud.get(db, id=req.id)
        if not updated_req:
            return

        if updated_req.status == ContactRequestStatus.PROCESSING:
            updated_req.status = ContactRequestStatus.IGNORED
            await db.commit()
            logger.info(
                "request_marked_ignored_no_acceptance",
                request_id=updated_req.id,
                from_qiao_id=user_qiao_id,
                to_qiao_id=updated_req.to_qiao_id,
            )

    except Exception as e:
        # Unexpected error in worker itself (not in _process_ai_contact_request)
        # This should rarely happen as _process_ai_contact_request handles its own errors
        logger.error(
            "worker_process_one_failed",
            request_id=req.id,
            user_qiao_id=req.from_qiao_id,
            to_qiao_id=req.to_qiao_id,
            error=str(e),
            exc_info=True,
        )
        # Mark as FAILED - this is a system error at worker level
        try:
            await db.refresh(req)
            req.status = ContactRequestStatus.FAILED
            await db.commit()
            logger.info(
                "request_marked_failed_worker_error",
                request_id=req.id,
            )
        except Exception as commit_error:
            logger.error(
                "failed_to_mark_failed_in_worker",
                request_id=req.id,
                error=str(commit_error),
            )


async def contact_request_worker_loop(poll_interval: float = 2.0, batch_size: int = 10) -> None:
    """
    Main worker loop.

    Polls for PENDING requests, marks them as PROCESSING, then processes each
    in a separate session to avoid long transactions.
    """
    logger.info("contact_request_worker_started", interval=poll_interval, batch_size=batch_size)
    session_factory = get_sessionmaker()
    try:
        while True:
            try:
                # Lock and mark as PROCESSING in one transaction
                async with session_factory() as db:
                    batch = await _lock_pending_requests(db, batch_size)

                if not batch:
                    await asyncio.sleep(poll_interval)
                    continue

                # Process each request with its own session
                for req in batch:
                    async with session_factory() as process_db:
                        await _process_one(process_db, req)

            except Exception as e:
                logger.error("contact_request_worker_iteration_failed", error=str(e), exc_info=True)
                # Backoff slightly on unexpected errors
                await asyncio.sleep(poll_interval)

    except asyncio.CancelledError:
        logger.info("contact_request_worker_cancelled")
    except Exception as e:
        logger.critical("contact_request_worker_crashed", error=str(e), exc_info=True)


def start_contact_request_worker(app: FastAPI) -> None:
    """
    Spawn the background worker task and keep a reference on app.state.
    """
    loop = asyncio.get_event_loop()
    task = loop.create_task(contact_request_worker_loop())
    app.state.contact_request_worker = task
    logger.info("contact_request_worker_spawned")

"""Background worker for message dispatch outbox."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_sessionmaker
from app.enums import (
    AlertDomain,
    AlertEventType,
    AlertSeverityLevel,
    MessageDeliveryStatus,
    MessageDispatchOutboxStatus,
    MessageDispatchOutboxType,
    MessageTransportProvider,
)
from app.models.message import (
    MessageDelivery,
    MessageDispatchOutbox,
    MessageEndpoint,
    MessageHistory,
)
from app.services.alerting.events import build_standard_alert_entities, emit_alert
from app.services.message.providers.factory import create_timeline_endpoint_sender
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

logger = get_logger(__name__)
_ALERT_SCHEMA_VERSION = 1
_WORKER_NAME = "dispatch_outbox_worker"

_IDLE_SCAN_INTERVAL_SECONDS = 1.0
_BUSY_SCAN_INTERVAL_SECONDS = 0.2
_BATCH_SIZE = 100
_LOCK_TIMEOUT_SECONDS = 60
_RETRY_DELAYS_SECONDS = (60, 300, 900)
_MAX_RETRY_ATTEMPTS = len(_RETRY_DELAYS_SECONDS)


class _DispatchOutboxWorkerState:
    """Track dispatch outbox worker status."""

    def __init__(self) -> None:
        self.task: asyncio.Task[None] | None = None
        self.running: bool = False


_worker_state = _DispatchOutboxWorkerState()


def _now_utc() -> datetime:
    return datetime.now(UTC)


async def start_dispatch_outbox_worker() -> None:
    """Start background worker for dispatch outbox."""
    if _worker_state.running:
        logger.warning("dispatch_outbox_worker_already_running")
        return

    _worker_state.running = True
    _worker_state.task = asyncio.create_task(_dispatch_outbox_loop())
    logger.info("dispatch_outbox_worker_started")


async def stop_dispatch_outbox_worker() -> None:
    """Stop dispatch outbox worker gracefully."""
    if not _worker_state.running:
        return

    _worker_state.running = False
    if _worker_state.task and not _worker_state.task.done():
        _worker_state.task.cancel()
        try:
            await _worker_state.task
        except asyncio.CancelledError:
            pass
    _worker_state.task = None
    logger.info("dispatch_outbox_worker_stopped")


async def _dispatch_outbox_loop() -> None:
    """Scan and process dispatch outbox rows."""
    while _worker_state.running:
        try:
            processed = await _scan_and_process_once()
            interval = _BUSY_SCAN_INTERVAL_SECONDS if processed else _IDLE_SCAN_INTERVAL_SECONDS
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("dispatch_outbox_worker_cancelled")
            break
        except Exception:
            logger.exception("dispatch_outbox_worker_loop_error")
            await emit_alert(
                event_type=AlertEventType.BACKGROUND_WORKER_FAILURE,
                domain=AlertDomain.BACKGROUND_WORKER,
                severity_level=AlertSeverityLevel.ERROR,
                dedupe_fields={
                    "worker_name": _WORKER_NAME,
                    "stage": "dispatch_outbox_loop",
                    "error_code": "BACKGROUND_WORKER_FAILURE",
                },
                details={
                    "schema_version": _ALERT_SCHEMA_VERSION,
                    "stage": "dispatch_outbox_loop",
                    "worker_name": _WORKER_NAME,
                    "error_code": "BACKGROUND_WORKER_FAILURE",
                },
                entities=build_standard_alert_entities(worker_name=_WORKER_NAME),
            )
            await asyncio.sleep(_IDLE_SCAN_INTERVAL_SECONDS)


async def _scan_and_process_once() -> int:
    """Claim a batch of outbox tasks and process them one by one."""
    session_factory = get_sessionmaker()
    task_ids: list[int] = []
    now = _now_utc()

    async with session_factory() as db:
        await _recover_stale_processing_tasks(db, now=now)
        task_ids = await _claim_pending_tasks(db, now=now)
        await db.commit()

    for task_id in task_ids:
        await _process_outbox_task(task_id)

    return len(task_ids)


async def _recover_stale_processing_tasks(db: AsyncSession, *, now: datetime) -> None:
    """Move stale PROCESSING tasks back to PENDING for retry."""
    stale_before = now - timedelta(seconds=_LOCK_TIMEOUT_SECONDS)
    await db.execute(
        update(MessageDispatchOutbox)
        .where(
            MessageDispatchOutbox.outbox_type == MessageDispatchOutboxType.TIMELINE_FANOUT,
            MessageDispatchOutbox.status == MessageDispatchOutboxStatus.PROCESSING,
            MessageDispatchOutbox.locked_at.is_not(None),
            MessageDispatchOutbox.locked_at <= stale_before,
        )
        .values(
            status=MessageDispatchOutboxStatus.PENDING,
            locked_at=None,
            next_retry_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )


async def _claim_pending_tasks(db: AsyncSession, *, now: datetime) -> list[int]:
    """Claim a batch of pending tasks using row-level locks."""
    result = await db.execute(
        select(MessageDispatchOutbox)
        .where(
            MessageDispatchOutbox.outbox_type == MessageDispatchOutboxType.TIMELINE_FANOUT,
            MessageDispatchOutbox.status == MessageDispatchOutboxStatus.PENDING,
            or_(
                MessageDispatchOutbox.next_retry_at.is_(None),
                MessageDispatchOutbox.next_retry_at <= now,
            ),
        )
        .order_by(MessageDispatchOutbox.created_at.asc(), MessageDispatchOutbox.id.asc())
        .limit(_BATCH_SIZE)
        .with_for_update(skip_locked=True)
    )
    tasks = list(result.scalars().all())
    for task in tasks:
        task.status = MessageDispatchOutboxStatus.PROCESSING
        task.locked_at = now
        db.add(task)
    await db.flush()
    return [int(task.id) for task in tasks]


async def _process_outbox_task(task_id: int) -> None:
    """Process one outbox row in an isolated database session."""
    session_factory = get_sessionmaker()
    async with session_factory() as db:
        try:
            result = await db.execute(
                select(MessageDispatchOutbox)
                .where(MessageDispatchOutbox.id == task_id)
                .with_for_update()
            )
            task = result.scalar_one_or_none()
            if task is None:
                return
            if task.status != MessageDispatchOutboxStatus.PROCESSING:
                return
            if task.outbox_type != MessageDispatchOutboxType.TIMELINE_FANOUT:
                task.status = MessageDispatchOutboxStatus.FAILED
                task.locked_at = None
                task.last_error_code = "UNSUPPORTED_OUTBOX_TYPE"
                task.last_error_detail = f"Unsupported outbox_type={task.outbox_type}"
                db.add(task)
                await db.commit()
                await emit_alert(
                    event_type=AlertEventType.MESSAGE_DISPATCH_TASK_FAILED,
                    domain=AlertDomain.MESSAGE_DISPATCH,
                    severity_level=AlertSeverityLevel.ERROR,
                    dedupe_fields={
                        "outbox_id": int(task.id),
                        "error_code": "MESSAGE_DISPATCH_UNSUPPORTED_OUTBOX_TYPE",
                    },
                    details={
                        "schema_version": _ALERT_SCHEMA_VERSION,
                        "stage": "process_outbox_task",
                        "error_code": "MESSAGE_DISPATCH_UNSUPPORTED_OUTBOX_TYPE",
                        "outbox_id": int(task.id),
                        "outbox_type": int(task.outbox_type),
                        "msg_id_server": task.msg_id_server,
                        "owner_user_id": int(task.owner_user_id),
                    },
                    entities=build_standard_alert_entities(
                        user_id=int(task.owner_user_id),
                        dispatch_outbox_id=int(task.id),
                        worker_name=_WORKER_NAME,
                    ),
                )
                return

            await _dispatch_timeline_task(db, task=task)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.exception("dispatch_outbox_task_failed", outbox_id=task_id)
            await emit_alert(
                event_type=AlertEventType.MESSAGE_DISPATCH_TASK_FAILED,
                domain=AlertDomain.MESSAGE_DISPATCH,
                severity_level=AlertSeverityLevel.ERROR,
                dedupe_fields={
                    "outbox_id": task_id,
                    "error_class": type(exc).__name__,
                    "error_code": "MESSAGE_DISPATCH_TASK_FAILED",
                },
                details={
                    "schema_version": _ALERT_SCHEMA_VERSION,
                    "stage": "process_outbox_task",
                    "error_code": "MESSAGE_DISPATCH_TASK_FAILED",
                    "error_class": type(exc).__name__,
                    "error_message": str(exc),
                    "outbox_id": task_id,
                },
                entities=build_standard_alert_entities(
                    dispatch_outbox_id=task_id,
                    worker_name=_WORKER_NAME,
                ),
            )


async def _dispatch_timeline_task(db: AsyncSession, *, task: MessageDispatchOutbox) -> None:
    """Dispatch one timeline fanout task and update retry status."""
    now = _now_utc()
    message_result = await db.execute(
        select(MessageHistory).where(MessageHistory.msg_id_server == task.msg_id_server)
    )
    message = message_result.scalar_one_or_none()
    if message is None:
        # Message may have been removed; mark as done to avoid retry loops.
        task.status = MessageDispatchOutboxStatus.DONE
        task.locked_at = None
        task.next_retry_at = None
        task.last_error_code = None
        task.last_error_detail = None
        db.add(task)
        return

    endpoints_result = await db.execute(
        select(MessageEndpoint).where(
            and_(
                MessageEndpoint.user_id == task.owner_user_id,
                or_(
                    MessageEndpoint.lease_expires_at.is_(None),
                    MessageEndpoint.lease_expires_at > now,
                ),
            )
        )
    )
    endpoints = list(endpoints_result.scalars().all())
    if not endpoints:
        task.status = MessageDispatchOutboxStatus.DONE
        task.locked_at = None
        task.next_retry_at = None
        task.last_error_code = None
        task.last_error_detail = None
        db.add(task)
        return

    first_error_code: str | None = None
    first_error_detail: str | None = None
    failed_count = 0

    for endpoint in endpoints:
        existing = await _get_delivery(
            db,
            msg_id_server=message.msg_id_server,
            endpoint_id=endpoint.id,
        )
        if existing is not None and existing.status == MessageDeliveryStatus.DISPATCHED:
            continue

        try:
            provider = MessageTransportProvider(int(endpoint.provider))
        except ValueError:
            failed_count += 1
            first_error_code = first_error_code or "UNSUPPORTED_PROVIDER"
            first_error_detail = first_error_detail or f"Unsupported provider={endpoint.provider}"
            await _upsert_delivery(
                db,
                msg_id_server=message.msg_id_server,
                endpoint=endpoint,
                status=MessageDeliveryStatus.FAILED,
                provider_msg_id=None,
                failed_reason_code="UNSUPPORTED_PROVIDER",
                failed_detail=f"Unsupported provider={endpoint.provider}",
            )
            continue

        sender = create_timeline_endpoint_sender(db, provider=provider)
        result = await sender.send_to_endpoint(endpoint=endpoint, message=message)

        if result.success:
            await _upsert_delivery(
                db,
                msg_id_server=message.msg_id_server,
                endpoint=endpoint,
                status=MessageDeliveryStatus.DISPATCHED,
                provider_msg_id=result.msg_id_provider,
                failed_reason_code=None,
                failed_detail=None,
            )
            continue

        failed_count += 1
        if first_error_code is None:
            first_error_code = result.error_code or "DISPATCH_FAILED"
            first_error_detail = result.error_message
        await _upsert_delivery(
            db,
            msg_id_server=message.msg_id_server,
            endpoint=endpoint,
            status=MessageDeliveryStatus.FAILED,
            provider_msg_id=result.msg_id_provider,
            failed_reason_code=result.error_code or "DISPATCH_FAILED",
            failed_detail=result.error_message,
        )

    if failed_count == 0:
        task.status = MessageDispatchOutboxStatus.DONE
        task.locked_at = None
        task.next_retry_at = None
        task.last_error_code = None
        task.last_error_detail = None
        db.add(task)
        return

    # Retry path (attempt_count tracks retries only, excluding initial dispatch)
    retry_count = int(task.attempt_count)
    task.last_error_code = first_error_code
    task.last_error_detail = first_error_detail
    task.locked_at = None

    if retry_count >= _MAX_RETRY_ATTEMPTS:
        task.status = MessageDispatchOutboxStatus.FAILED
        task.next_retry_at = None
        await emit_alert(
            event_type=AlertEventType.MESSAGE_DISPATCH_RETRY_EXHAUSTED,
            domain=AlertDomain.MESSAGE_DISPATCH,
            severity_level=AlertSeverityLevel.ERROR,
            dedupe_fields={
                "outbox_id": int(task.id),
                "error_code": first_error_code or "DISPATCH_FAILED",
            },
            details={
                "schema_version": _ALERT_SCHEMA_VERSION,
                "stage": "dispatch_timeline_task",
                "error_code": "MESSAGE_DISPATCH_RETRY_EXHAUSTED",
                "last_error_code": first_error_code,
                "last_error_detail": first_error_detail,
                "outbox_id": int(task.id),
                "msg_id_server": task.msg_id_server,
                "owner_user_id": int(task.owner_user_id),
                "attempt_count": retry_count,
                "max_retry_attempts": _MAX_RETRY_ATTEMPTS,
            },
            entities=build_standard_alert_entities(
                user_id=int(task.owner_user_id),
                dispatch_outbox_id=int(task.id),
                worker_name=_WORKER_NAME,
            ),
        )
    else:
        retry_count += 1
        task.attempt_count = retry_count
        task.status = MessageDispatchOutboxStatus.PENDING
        delay_seconds = _RETRY_DELAYS_SECONDS[min(retry_count - 1, len(_RETRY_DELAYS_SECONDS) - 1)]
        task.next_retry_at = now + timedelta(seconds=delay_seconds)

    db.add(task)


async def _get_delivery(
    db: AsyncSession,
    *,
    msg_id_server: str,
    endpoint_id: int,
) -> MessageDelivery | None:
    result = await db.execute(
        select(MessageDelivery).where(
            MessageDelivery.msg_id_server == msg_id_server,
            MessageDelivery.endpoint_id == endpoint_id,
        )
    )
    return result.scalar_one_or_none()


async def _upsert_delivery(
    db: AsyncSession,
    *,
    msg_id_server: str,
    endpoint: MessageEndpoint,
    status: MessageDeliveryStatus,
    provider_msg_id: str | None,
    failed_reason_code: str | None,
    failed_detail: str | None,
) -> None:
    now = _now_utc()
    try:
        async with db.begin_nested():
            db.add(
                MessageDelivery(
                    id=generate_snowflake_id(),
                    msg_id_server=msg_id_server,
                    endpoint_id=endpoint.id,
                    provider=endpoint.provider,
                    target_key=endpoint.target_key,
                    provider_msg_id=provider_msg_id,
                    status=status,
                    dispatched_at=now if status == MessageDeliveryStatus.DISPATCHED else None,
                    failed_reason_code=failed_reason_code,
                    failed_detail=failed_detail,
                )
            )
            await db.flush()
            return
    except IntegrityError:
        pass

    existing = await _get_delivery(db, msg_id_server=msg_id_server, endpoint_id=endpoint.id)
    if existing is None:
        return
    existing.provider = endpoint.provider
    existing.target_key = endpoint.target_key
    existing.provider_msg_id = provider_msg_id
    existing.status = status
    existing.dispatched_at = now if status == MessageDeliveryStatus.DISPATCHED else None
    existing.failed_reason_code = failed_reason_code
    existing.failed_detail = failed_detail
    db.add(existing)
    await db.flush()

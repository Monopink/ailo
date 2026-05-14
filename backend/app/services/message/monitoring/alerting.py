"""WebSocket runtime threshold monitoring worker."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_sessionmaker
from app.enums import (
    AlertDomain,
    AlertEventType,
    AlertSeverityLevel,
    MessageDeliveryStatus,
    MessageDispatchOutboxStatus,
    MessageEndpointScope,
    MessageTransportProvider,
)
from app.models.message import (
    MessageDelivery,
    MessageDevice,
    MessageDispatchOutbox,
    MessageEndpoint,
)
from app.services.alerting.events import build_standard_alert_entities, emit_alert
from app.services.message.monitoring.client_runtime_alerting import (
    emit_domain_misconfig_alert_if_needed,
)
from app.services.message.websocket.manager import ws_manager
from app.type_defs import JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)

_WORKER_NAME = "message_ws_alerting_worker"
_ALERT_SCHEMA_VERSION = 1
_SCAN_INTERVAL_SECONDS = 30
_SEND_FAILURE_WINDOW_SECONDS = 300
_ACK_P95_SAMPLE_WINDOW_SECONDS = 600

_ACTIVE_ENDPOINT_THRESHOLD = 1200
_OUTBOX_BACKLOG_THRESHOLD = 400
_SEND_FAILURE_THRESHOLD = 20
_ACK_P95_THRESHOLD_MS = 15000


async def _count_active_websocket_endpoints(db: AsyncSession, *, now: datetime) -> int:
    result = await db.execute(
        select(func.count(MessageEndpoint.id)).where(
            and_(
                MessageEndpoint.provider == MessageTransportProvider.WEBSOCKET,
                or_(
                    MessageEndpoint.lease_expires_at.is_(None),
                    MessageEndpoint.lease_expires_at > now,
                ),
            )
        )
    )
    return int(result.scalar_one() or 0)


async def _count_outbox_backlog(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count(MessageDispatchOutbox.id)).where(
            MessageDispatchOutbox.status.in_(
                (
                    MessageDispatchOutboxStatus.PENDING,
                    MessageDispatchOutboxStatus.PROCESSING,
                )
            )
        )
    )
    return int(result.scalar_one() or 0)


async def _count_ws_send_failed(db: AsyncSession, *, now: datetime) -> int:
    window_start = now - timedelta(seconds=_SEND_FAILURE_WINDOW_SECONDS)
    result = await db.execute(
        select(func.count(MessageDelivery.id)).where(
            and_(
                MessageDelivery.provider == MessageTransportProvider.WEBSOCKET,
                MessageDelivery.status == MessageDeliveryStatus.FAILED,
                MessageDelivery.failed_reason_code == "WS_SEND_FAILED",
                MessageDelivery.created_at >= window_start,
            )
        )
    )
    return int(result.scalar_one() or 0)


async def _ack_p95_latency_ms(db: AsyncSession, *, now: datetime) -> float | None:
    window_start = now - timedelta(seconds=_ACK_P95_SAMPLE_WINDOW_SECONDS)
    ack_latency_ms = func.greatest(
        func.extract("epoch", MessageDevice.updated_at - MessageDevice.last_acked_msg_sent_at)
        * 1000.0,
        0.0,
    )
    result = await db.execute(
        select(func.percentile_cont(0.95).within_group(ack_latency_ms))
        .select_from(MessageDevice)
        .join(
            MessageEndpoint,
            and_(
                MessageEndpoint.user_id == MessageDevice.user_id,
                MessageEndpoint.device_id == MessageDevice.device_id,
            ),
        )
        .where(
            MessageEndpoint.provider == MessageTransportProvider.WEBSOCKET,
            MessageEndpoint.endpoint_scope == MessageEndpointScope.DEVICE,
            or_(
                MessageEndpoint.lease_expires_at.is_(None),
                MessageEndpoint.lease_expires_at > now,
            ),
            MessageDevice.last_acked_msg_sent_at.is_not(None),
            MessageDevice.updated_at >= MessageDevice.last_acked_msg_sent_at,
            MessageDevice.updated_at >= window_start,
        )
    )
    value = result.scalar_one_or_none()
    if value is None:
        return None
    return float(value)


async def _emit_threshold_alert(
    *,
    event_type: AlertEventType,
    severity_level: AlertSeverityLevel,
    metric_name: str,
    threshold_value: int,
    metric_value: float,
    details: JSONDict,
) -> None:
    payload: JSONDict = {
        "schema_version": _ALERT_SCHEMA_VERSION,
        "worker_name": _WORKER_NAME,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "threshold_value": threshold_value,
        **details,
    }
    await emit_alert(
        event_type=event_type,
        domain=AlertDomain.MESSAGE_WEBSOCKET,
        severity_level=severity_level,
        dedupe_fields={
            "worker_name": _WORKER_NAME,
            "metric_name": metric_name,
            "threshold_value": threshold_value,
        },
        details=payload,
        entities=build_standard_alert_entities(worker_name=_WORKER_NAME),
    )


async def _run_once() -> None:
    now = datetime.now(UTC)
    ws_send_queue_full_count = ws_manager.drain_send_queue_full_count()

    session_factory = get_sessionmaker()
    async with session_factory() as db:
        active_endpoint_count = await _count_active_websocket_endpoints(db, now=now)
        outbox_backlog_count = await _count_outbox_backlog(db)
        ws_send_failed_count = await _count_ws_send_failed(db, now=now)
        ack_p95_latency_ms = await _ack_p95_latency_ms(db, now=now)
        await emit_domain_misconfig_alert_if_needed(db, now=now)

    ws_send_failure_count = ws_send_queue_full_count + ws_send_failed_count

    if active_endpoint_count >= _ACTIVE_ENDPOINT_THRESHOLD:
        await _emit_threshold_alert(
            event_type=AlertEventType.MESSAGE_WS_ACTIVE_ENDPOINT_THRESHOLD_EXCEEDED,
            severity_level=AlertSeverityLevel.WARNING,
            metric_name="active_websocket_endpoint_count",
            threshold_value=_ACTIVE_ENDPOINT_THRESHOLD,
            metric_value=float(active_endpoint_count),
            details={
                "measured_at_ms": int(now.timestamp() * 1000),
            },
        )

    if outbox_backlog_count >= _OUTBOX_BACKLOG_THRESHOLD:
        await _emit_threshold_alert(
            event_type=AlertEventType.MESSAGE_WS_OUTBOX_BACKLOG_THRESHOLD_EXCEEDED,
            severity_level=AlertSeverityLevel.ERROR,
            metric_name="dispatch_outbox_backlog_count",
            threshold_value=_OUTBOX_BACKLOG_THRESHOLD,
            metric_value=float(outbox_backlog_count),
            details={
                "measured_at_ms": int(now.timestamp() * 1000),
                "included_statuses": [
                    int(MessageDispatchOutboxStatus.PENDING),
                    int(MessageDispatchOutboxStatus.PROCESSING),
                ],
            },
        )

    if ws_send_failure_count >= _SEND_FAILURE_THRESHOLD:
        await _emit_threshold_alert(
            event_type=AlertEventType.MESSAGE_WS_SEND_FAILURE_THRESHOLD_EXCEEDED,
            severity_level=AlertSeverityLevel.ERROR,
            metric_name="ws_send_failure_count",
            threshold_value=_SEND_FAILURE_THRESHOLD,
            metric_value=float(ws_send_failure_count),
            details={
                "measured_at_ms": int(now.timestamp() * 1000),
                "window_seconds": _SEND_FAILURE_WINDOW_SECONDS,
                "ws_send_queue_full_count": ws_send_queue_full_count,
                "ws_send_failed_count": ws_send_failed_count,
            },
        )

    if ack_p95_latency_ms is not None and ack_p95_latency_ms >= _ACK_P95_THRESHOLD_MS:
        await _emit_threshold_alert(
            event_type=AlertEventType.MESSAGE_WS_ACK_P95_THRESHOLD_EXCEEDED,
            severity_level=AlertSeverityLevel.WARNING,
            metric_name="message_ack_latency_p95_ms",
            threshold_value=_ACK_P95_THRESHOLD_MS,
            metric_value=ack_p95_latency_ms,
            details={
                "measured_at_ms": int(now.timestamp() * 1000),
                "sample_window_seconds": _ACK_P95_SAMPLE_WINDOW_SECONDS,
            },
        )


async def _monitoring_loop() -> None:
    while True:
        try:
            await _run_once()
        except Exception:
            logger.error("message_ws_alerting_loop_failed", exc_info=True)
        await asyncio.sleep(_SCAN_INTERVAL_SECONDS)


def start_message_ws_alerting_worker(app: FastAPI) -> None:
    """Start WebSocket alerting worker."""
    task = asyncio.create_task(_monitoring_loop())
    app.state.message_ws_alerting_task = task
    logger.info("message_ws_alerting_worker_started", interval_seconds=_SCAN_INTERVAL_SECONDS)


async def stop_message_ws_alerting_worker(app: FastAPI) -> None:
    """Stop WebSocket alerting worker."""
    task: asyncio.Task[None] | None = getattr(app.state, "message_ws_alerting_task", None)
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:  # pragma: no cover - expected shutdown flow
        pass
    logger.info("message_ws_alerting_worker_stopped")

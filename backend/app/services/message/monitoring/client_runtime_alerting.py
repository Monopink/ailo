"""Client runtime observation based alerting for message websocket failures."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AlertDomain, AlertEventType, AlertSeverityLevel
from app.models.system import ClientRuntimeObservation
from app.services.alerting.events import build_standard_alert_entities, emit_alert
from app.type_defs import JSONDict

_WINDOW_SECONDS = 300
_DOMAIN_MISCONFIG_THRESHOLD = 8


async def _count_domain_misconfig_events(db: AsyncSession, *, now: datetime) -> int:
    window_start = now - timedelta(seconds=_WINDOW_SECONDS)
    result = await db.execute(
        select(func.count(ClientRuntimeObservation.id)).where(
            and_(
                ClientRuntimeObservation.client_type == "mp_weixin",
                ClientRuntimeObservation.entry_source == "message_service",
                ClientRuntimeObservation.event_name == "message_connect_failed",
                ClientRuntimeObservation.event_payload["error_code"].astext
                == "WS_DOMAIN_NOT_ALLOWED",
                ClientRuntimeObservation.occurred_at >= window_start,
            )
        )
    )
    return int(result.scalar_one() or 0)


async def emit_domain_misconfig_alert_if_needed(db: AsyncSession, *, now: datetime) -> None:
    """Emit alert when domain-misconfiguration failures exceed threshold."""
    failure_count = await _count_domain_misconfig_events(db, now=now)
    if failure_count < _DOMAIN_MISCONFIG_THRESHOLD:
        return

    details: JSONDict = {
        "schema_version": 1,
        "metric_name": "client_ws_domain_misconfig_count",
        "metric_value": failure_count,
        "threshold_value": _DOMAIN_MISCONFIG_THRESHOLD,
        "window_seconds": _WINDOW_SECONDS,
        "measured_at_ms": int(now.timestamp() * 1000),
        "source": "client_runtime_observations",
    }
    await emit_alert(
        event_type=AlertEventType.MESSAGE_WS_CLIENT_DOMAIN_MISCONFIG_THRESHOLD_EXCEEDED,
        domain=AlertDomain.MESSAGE_WEBSOCKET,
        severity_level=AlertSeverityLevel.ERROR,
        dedupe_fields={
            "metric_name": "client_ws_domain_misconfig_count",
            "threshold_value": _DOMAIN_MISCONFIG_THRESHOLD,
            "window_seconds": _WINDOW_SECONDS,
        },
        details=details,
        entities=build_standard_alert_entities(worker_name="message_ws_alerting_worker"),
    )


__all__ = ["emit_domain_misconfig_alert_if_needed"]

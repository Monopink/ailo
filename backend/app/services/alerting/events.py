"""Unified alert-event emission helpers.

This module centralizes business alert writes so callers share
consistent dedupe keys, details contracts, and entity references.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from app.core.database import get_sessionmaker
from app.crud.system.alerting import alert_events
from app.enums import AlertDomain, AlertEntityType, AlertEventType, AlertSeverityLevel
from app.type_defs import JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)

_DETAILS_SCHEMA_VERSION = 1
_DEDUPE_KEY_MAX_LEN = 255
_DEDUPE_PREFIX_MAX_LEN = 180
_QIAO_ENTITY_PREFIX = "qiao_id:"

_ERROR_CODE_BY_EVENT: dict[AlertEventType, str] = {
    AlertEventType.MEMORY_REFRESH_MISS_THRESHOLD_EXCEEDED: "MEMORY_REFRESH_MISS_THRESHOLD_EXCEEDED",
    AlertEventType.AI_CONVERSATION_CONTEXT_CONFIG_INVALID: "AI_CONVERSATION_CONTEXT_CONFIG_INVALID",
    AlertEventType.AI_CONVERSATION_RETRY_CONFIG_INVALID: "AI_CONVERSATION_RETRY_CONFIG_INVALID",
    AlertEventType.AI_CONVERSATION_SYSTEM_FAILURE: "AI_CONVERSATION_SYSTEM_FAILURE",
    AlertEventType.MESSAGE_DISPATCH_RETRY_EXHAUSTED: "MESSAGE_DISPATCH_RETRY_EXHAUSTED",
    AlertEventType.MESSAGE_DISPATCH_TASK_FAILED: "MESSAGE_DISPATCH_TASK_FAILED",
    AlertEventType.MESSAGE_WS_ACTIVE_ENDPOINT_THRESHOLD_EXCEEDED: (
        "MESSAGE_WS_ACTIVE_ENDPOINT_THRESHOLD_EXCEEDED"
    ),
    AlertEventType.MESSAGE_WS_OUTBOX_BACKLOG_THRESHOLD_EXCEEDED: (
        "MESSAGE_WS_OUTBOX_BACKLOG_THRESHOLD_EXCEEDED"
    ),
    AlertEventType.MESSAGE_WS_SEND_FAILURE_THRESHOLD_EXCEEDED: (
        "MESSAGE_WS_SEND_FAILURE_THRESHOLD_EXCEEDED"
    ),
    AlertEventType.MESSAGE_WS_ACK_P95_THRESHOLD_EXCEEDED: "MESSAGE_WS_ACK_P95_THRESHOLD_EXCEEDED",
    AlertEventType.BACKGROUND_WORKER_FAILURE: "BACKGROUND_WORKER_FAILURE",
}


def _coerce_dedupe_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float | str):
        return str(value)
    return str(value)


def _build_dedupe_key(dedupe_fields: Mapping[str, object] | None) -> str:
    dedupe_components: dict[str, str] = {
        "date_bucket_utc": datetime.now(UTC).date().isoformat(),
    }
    if dedupe_fields:
        for key in sorted(dedupe_fields):
            dedupe_components[key] = _coerce_dedupe_value(dedupe_fields[key])

    raw = "|".join(f"{key}={dedupe_components[key]}" for key in sorted(dedupe_components))
    if len(raw) <= _DEDUPE_KEY_MAX_LEN:
        return raw

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    truncated = raw[:_DEDUPE_PREFIX_MAX_LEN]
    return f"{truncated}|sha256={digest}"[:_DEDUPE_KEY_MAX_LEN]


def _normalize_details(
    *,
    event_type: AlertEventType,
    details: JSONDict | None,
    error_code: str | None,
) -> JSONDict:
    normalized: JSONDict = dict(details or {})

    schema_version = normalized.get("schema_version")
    if not isinstance(schema_version, int):
        logger.error(
            "alert_details_schema_version_invalid",
            event_type=str(event_type),
            schema_version_type=type(schema_version).__name__,
        )
        normalized["schema_version"] = _DETAILS_SCHEMA_VERSION

    resolved_error_code = error_code or _ERROR_CODE_BY_EVENT.get(event_type, "ALERT_UNKNOWN_ERROR")
    normalized.setdefault("error_code", resolved_error_code)
    return normalized


def build_standard_alert_entities(
    *,
    instance_id: int | None = None,
    instance_qiao_id: str | None = None,
    user_id: int | None = None,
    user_qiao_id: str | None = None,
    buffer_id: int | None = None,
    dispatch_outbox_id: int | None = None,
    worker_name: str | None = None,
) -> list[tuple[AlertEntityType, str]]:
    """Build normalized alert entity references for common runtime objects."""
    entities: list[tuple[AlertEntityType, str]] = []

    if isinstance(instance_id, int):
        entities.append((AlertEntityType.AI_INSTANCE, str(instance_id)))
    if isinstance(instance_qiao_id, str) and instance_qiao_id:
        entities.append((AlertEntityType.AI_INSTANCE, f"{_QIAO_ENTITY_PREFIX}{instance_qiao_id}"))
    if isinstance(user_id, int):
        entities.append((AlertEntityType.USER, str(user_id)))
    if isinstance(user_qiao_id, str) and user_qiao_id:
        entities.append((AlertEntityType.USER, f"{_QIAO_ENTITY_PREFIX}{user_qiao_id}"))
    if isinstance(buffer_id, int):
        entities.append((AlertEntityType.AI_MESSAGE_BUFFER, str(buffer_id)))
    if isinstance(dispatch_outbox_id, int):
        entities.append((AlertEntityType.MESSAGE_DISPATCH_OUTBOX, str(dispatch_outbox_id)))
    if isinstance(worker_name, str) and worker_name:
        entities.append((AlertEntityType.BACKGROUND_WORKER, worker_name))

    deduped: list[tuple[AlertEntityType, str]] = []
    seen: set[tuple[AlertEntityType, str]] = set()
    for entity in entities:
        if entity in seen:
            continue
        seen.add(entity)
        deduped.append(entity)
    return deduped


async def emit_alert(
    *,
    event_type: AlertEventType,
    domain: AlertDomain,
    severity_level: AlertSeverityLevel,
    details: JSONDict | None,
    dedupe_fields: Mapping[str, object] | None = None,
    entities: Sequence[tuple[AlertEntityType, str]] = (),
    error_code: str | None = None,
) -> bool:
    """Persist one business alert in best-effort mode."""
    normalized_details = _normalize_details(
        event_type=event_type,
        details=details,
        error_code=error_code,
    )
    dedupe_key = _build_dedupe_key(dedupe_fields)
    rows = [(str(entity_type), entity_id) for entity_type, entity_id in entities]

    session_factory = get_sessionmaker()
    try:
        async with session_factory() as db:
            inserted = await alert_events.insert_unique_with_entities(
                db,
                event_type=str(event_type),
                domain=str(domain),
                severity_level=int(severity_level),
                dedupe_key=dedupe_key,
                details=normalized_details,
                entities=rows,
            )
            await db.commit()
            return inserted
    except Exception as exc:
        logger.error(
            "emit_alert_failed",
            event_type=str(event_type),
            domain=str(domain),
            error=str(exc),
            exc_info=True,
        )
        return False


__all__ = ["build_standard_alert_entities", "emit_alert"]

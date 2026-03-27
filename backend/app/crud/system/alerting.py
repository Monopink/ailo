"""CRUD helpers for alerting tables (alert_events, alert_event_entities)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system.alerting import AlertEvent, AlertEventEntity
from app.type_defs import JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)

_DETAILS_MAX_BYTES = 16 * 1024


def _safe_details(details: JSONDict | None) -> JSONDict | None:
    if details is None:
        return None

    try:
        payload = json.dumps(details, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception:
        logger.error("alert_event_details_serialize_failed")
        return {"schema_version": 1, "truncated": True, "truncated_reason": "serialize_failed"}

    if len(payload.encode("utf-8")) <= _DETAILS_MAX_BYTES:
        return details

    logger.error(
        "alert_event_details_too_large",
        size_bytes=len(payload.encode("utf-8")),
        max_bytes=_DETAILS_MAX_BYTES,
    )
    return {"schema_version": 1, "truncated": True, "truncated_reason": "size_limit_exceeded"}


class CRUDAlertEvent:
    """CRUD helpers for alert_events and alert_event_entities."""

    async def insert_unique_with_entities(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        domain: str,
        severity_level: int,
        dedupe_key: str | None,
        details: JSONDict | None,
        entities: Sequence[tuple[str, str]],
    ) -> bool:
        """Insert one alert event row with entity references.

        Returns False when a dedupe conflict happens (audit-only semantics).
        """
        sanitized_details = _safe_details(details)

        result = await db.execute(
            insert(AlertEvent)
            .values(
                event_type=event_type,
                domain=domain,
                severity_level=severity_level,
                dedupe_key=dedupe_key,
                details=sanitized_details,
            )
            .on_conflict_do_nothing(
                index_elements=["event_type", "dedupe_key"],
                index_where=(AlertEvent.dedupe_key.isnot(None)),
            )
            .returning(AlertEvent.id)
        )
        event_id = result.scalar_one_or_none()
        if event_id is None:
            return False

        if entities:
            rows = [
                {
                    "event_id": int(event_id),
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                }
                for (entity_type, entity_id) in entities
            ]
            await db.execute(insert(AlertEventEntity).values(rows))

        return True

    async def cleanup_old(
        self,
        db: AsyncSession,
        *,
        retention_days: int,
        batch_size: int = 2000,
    ) -> int:
        """Delete old alert events (and their entity references) by created_at cutoff."""
        if retention_days <= 0:
            return 0

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        ids_result = await db.execute(
            select(AlertEvent.id)
            .where(AlertEvent.created_at < cutoff)
            .order_by(AlertEvent.created_at.asc())
            .limit(batch_size)
        )
        event_ids = [int(v) for v in ids_result.scalars().all()]
        if not event_ids:
            return 0

        await db.execute(delete(AlertEventEntity).where(AlertEventEntity.event_id.in_(event_ids)))
        result = await db.execute(delete(AlertEvent).where(AlertEvent.id.in_(event_ids)))
        deleted = int(result.rowcount or 0)
        logger.info(
            "alert_events_cleaned_up",
            retention_days=retention_days,
            deleted=deleted,
            batch_size=batch_size,
        )
        return deleted


alert_events = CRUDAlertEvent()

__all__ = ["CRUDAlertEvent", "alert_events"]

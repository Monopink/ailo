"""AI memory alerting helpers.

This module provides best-effort business alert events for memory refresh miss thresholds.
It must not block message sending or memory side effects.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.crud.system.alerting import alert_events
from app.enums import AlertDomain, AlertEntityType, AlertEventType, AlertSeverityLevel
from app.models.ai.memory import AIInstanceMemory
from app.services.ai.memory.operations import MemoryRefreshExecution
from app.type_defs import InstanceContext, JSONDict, JSONValue
from app.utils.logging import get_logger

logger = get_logger(__name__)

_THRESHOLD_TOTAL = 2
_THRESHOLD_RATIO_BP = 5000


def _coerce_raw_refresh_ids_sample(value: object) -> list[JSONValue]:
    if not isinstance(value, list):
        return []
    sample: list[JSONValue] = []
    for item in value[:10]:
        if item is None:
            sample.append(None)
            continue
        if isinstance(item, bool | int | float | str):
            sample.append(item)
            continue
        sample.append(str(item))
    return sample


def _build_refresh_ids_raw_diagnostics(raw_refresh_ids: object) -> tuple[int, int]:
    """Return (invalid_id_count, duplicates_dropped_count) from raw LLM output."""
    if not isinstance(raw_refresh_ids, list):
        return 0, 0

    invalid = 0
    seen: set[int] = set()
    duplicates = 0

    for item in raw_refresh_ids:
        if not isinstance(item, str):
            invalid += 1
            continue
        stripped = item.strip()
        if not stripped or not stripped.isdigit():
            invalid += 1
            continue
        memory_id = int(stripped)
        if memory_id in seen:
            duplicates += 1
            continue
        seen.add(memory_id)

    return invalid, duplicates


def _details_size_bytes(details: JSONDict) -> int:
    payload = json.dumps(details, ensure_ascii=False, separators=(",", ":"), default=str)
    return len(payload.encode("utf-8"))


async def maybe_write_refresh_miss_alert(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    context: InstanceContext,
    llm_request_id: int | None,
    task_turn_version: int,
    refresh_exec: MemoryRefreshExecution,
    raw_refresh_ids: object,
) -> None:
    """Best-effort write of a refresh miss threshold alert."""
    if refresh_exec.total <= 0:
        return

    async with session_factory() as db:
        if refresh_exec.total < _THRESHOLD_TOTAL:
            return
        if refresh_exec.miss_ratio_bp < _THRESHOLD_RATIO_BP:
            return

        invalid_id_count, duplicates_dropped_count = _build_refresh_ids_raw_diagnostics(
            raw_refresh_ids
        )

        now = datetime.now(UTC)
        candidate_filter = (
            AIInstanceMemory.user_qiao_id == context["user_qiao_id"],
            AIInstanceMemory.instance_qiao_id == context["instance_qiao_id"],
            AIInstanceMemory.status == 1,
            AIInstanceMemory.memory_type == "recent",
            (AIInstanceMemory.expires_at.is_(None) | (AIInstanceMemory.expires_at > now)),
        )
        count_stmt = select(func.count()).select_from(AIInstanceMemory).where(*candidate_filter)
        candidate_count = int((await db.execute(count_stmt)).scalar() or 0)
        candidate_ids_sample = list(
            (
                await db.execute(
                    select(AIInstanceMemory.id)
                    .where(*candidate_filter)
                    .order_by(
                        AIInstanceMemory.importance.desc(), AIInstanceMemory.created_at.desc()
                    )
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )

        details: JSONDict = {
            "schema_version": 1,
            "refresh_ids_raw_sample": _coerce_raw_refresh_ids_sample(raw_refresh_ids),
            "refresh_ids_normalized": cast(list[JSONValue], refresh_exec.attempted_ids),
            "hit_ids": cast(list[JSONValue], refresh_exec.hit_ids),
            "miss_ids": cast(list[JSONValue], refresh_exec.miss_ids),
            "invalid_id_count": invalid_id_count,
            "duplicates_dropped_count": duplicates_dropped_count,
            "candidate_recent_count": candidate_count,
            "candidate_recent_ids_sample": cast(list[JSONValue], candidate_ids_sample),
        }

        inserted = await alert_events.insert_unique_with_entities(
            db,
            event_type=str(AlertEventType.MEMORY_REFRESH_MISS_THRESHOLD_EXCEEDED),
            domain=str(AlertDomain.AI_MEMORY),
            severity_level=int(AlertSeverityLevel.WARNING),
            dedupe_key=f"instance_id={int(context['instance_id'])}|task_turn_version={task_turn_version}",
            details=details,
            entities=[
                (str(AlertEntityType.AI_INSTANCE), str(int(context["instance_id"]))),
                (str(AlertEntityType.USER), str(int(context["user_id"]))),
            ],
        )
        if inserted:
            logger.warning(
                "memory_refresh_miss_threshold_exceeded",
                instance_qiao_id=context["instance_qiao_id"],
                user_qiao_id=context["user_qiao_id"],
                task_turn_version=task_turn_version,
                llm_request_id=llm_request_id,
                refresh_total=refresh_exec.total,
                refresh_miss=refresh_exec.miss,
                refresh_miss_ratio_bp=refresh_exec.miss_ratio_bp,
                threshold_total=_THRESHOLD_TOTAL,
                threshold_ratio_bp=_THRESHOLD_RATIO_BP,
                details_size_bytes=_details_size_bytes(details),
            )

        await db.commit()

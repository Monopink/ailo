"""Admin operations for manual security IP block management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import IPBlockStatus
from app.models.security import SecurityIPBlock
from app.services.security.ip_block_repository import find_active_block_by_target_network
from app.services.security.ip_network_target import normalize_block_target
from app.type_defs import JSONDict

_MANUAL_BLOCK_RULE_CODE = "manual_block"
_MANUAL_BLOCK_REASON_CODE = "manual_block"
_MANUAL_BLOCK_SOURCE = "admin_manual"
_MANUAL_BLOCK_RULE_VERSION = "manual_v1"
_MAX_RELEASE_REASON_LENGTH = 128
_PERMANENT_EXPIRES_AT = datetime(9999, 12, 31, 23, 59, 59, tzinfo=UTC)


@dataclass(slots=True, frozen=True)
class NormalizedBlockTarget:
    target_network: str
    target_type: str
    display_target: str


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _normalize_target(target: str) -> NormalizedBlockTarget:
    normalized = normalize_block_target(target)
    return NormalizedBlockTarget(
        target_network=normalized.target_network,
        target_type=normalized.target_type,
        display_target=normalized.display_target,
    )


def _resolve_expiry(*, is_permanent: bool, ttl_seconds: int | None) -> tuple[datetime, int | None]:
    if is_permanent:
        return _PERMANENT_EXPIRES_AT, None
    if ttl_seconds is None:
        raise ValueError("ttl_required")
    if ttl_seconds <= 0:
        raise ValueError("ttl_invalid")
    return _now_utc() + timedelta(seconds=ttl_seconds), ttl_seconds


def _normalize_release_reason(release_reason: str) -> str:
    normalized = release_reason.strip()
    if normalized == "":
        raise ValueError("release_reason_required")
    return normalized[:_MAX_RELEASE_REASON_LENGTH]


def _normalize_severity_level(severity_level: int) -> int:
    if severity_level not in (1, 2, 3, 4):
        raise ValueError("severity_level_invalid")
    return severity_level


async def upsert_manual_ip_block(
    db: AsyncSession,
    *,
    target: str,
    severity_level: int,
    reason: str,
    is_permanent: bool,
    ttl_seconds: int | None,
    request_path: str,
    request_method: str,
    commit: bool = False,
) -> SecurityIPBlock:
    normalized_severity_level = _normalize_severity_level(severity_level)
    normalized_target = _normalize_target(target)
    now = _now_utc()
    expires_at, resolved_ttl_seconds = _resolve_expiry(
        is_permanent=is_permanent,
        ttl_seconds=ttl_seconds,
    )
    manual_reason = reason.strip()
    if manual_reason == "":
        raise ValueError("reason_required")

    existing_block = await find_active_block_by_target_network(
        db,
        target_network=normalized_target.target_network,
        now=now,
        for_update=True,
    )

    evidence_payload: JSONDict = {
        "manual_reason": manual_reason,
        "target_type": normalized_target.target_type,
        "target": normalized_target.display_target,
        "is_permanent": is_permanent,
        "ttl_seconds": resolved_ttl_seconds,
    }

    if existing_block is not None:
        existing_block.severity_level = normalized_severity_level
        existing_block.reason_code = _MANUAL_BLOCK_REASON_CODE
        existing_block.rule_code = _MANUAL_BLOCK_RULE_CODE
        existing_block.rule_version = _MANUAL_BLOCK_RULE_VERSION
        existing_block.source = _MANUAL_BLOCK_SOURCE
        existing_block.request_path = request_path[:255]
        existing_block.request_method = request_method[:16]
        existing_block.evidence_payload = evidence_payload
        existing_block.expires_at = expires_at
        existing_block.blocked_at = now
        existing_block.hit_count = int(existing_block.hit_count) + 1
        existing_block.status = int(IPBlockStatus.ACTIVE)
        existing_block.released_at = None
        existing_block.release_reason = None
        db.add(existing_block)
        if commit:
            await db.commit()
        else:
            await db.flush()
        await db.refresh(existing_block)
        return existing_block

    block = SecurityIPBlock(
        target_network=normalized_target.target_network,
        severity_level=normalized_severity_level,
        reason_code=_MANUAL_BLOCK_REASON_CODE,
        rule_code=_MANUAL_BLOCK_RULE_CODE,
        rule_version=_MANUAL_BLOCK_RULE_VERSION,
        source=_MANUAL_BLOCK_SOURCE,
        request_path=request_path[:255],
        request_method=request_method[:16],
        evidence_payload=evidence_payload,
        hit_count=1,
        first_hit_at=now,
        blocked_at=now,
        expires_at=expires_at,
        status=int(IPBlockStatus.ACTIVE),
        released_at=None,
        release_reason=None,
    )
    db.add(block)
    if commit:
        await db.commit()
    else:
        await db.flush()
    await db.refresh(block)
    return block


async def release_ip_block(
    db: AsyncSession,
    *,
    block_id: int,
    release_reason: str,
    commit: bool = False,
) -> SecurityIPBlock:
    normalized_reason = _normalize_release_reason(release_reason)
    result = await db.execute(
        select(SecurityIPBlock).where(SecurityIPBlock.id == block_id).limit(1).with_for_update()
    )
    block = result.scalar_one_or_none()
    if block is None:
        raise ValueError("block_not_found")
    if int(block.status) != int(IPBlockStatus.ACTIVE):
        raise ValueError("block_not_active")
    if block.expires_at <= _now_utc():
        raise ValueError("block_not_effective")

    now = _now_utc()
    block.status = int(IPBlockStatus.RELEASED)
    block.released_at = now
    block.release_reason = normalized_reason
    db.add(block)
    if commit:
        await db.commit()
    else:
        await db.flush()
    await db.refresh(block)
    return block

"""Security enforcement pipeline for attack detection, logging, and punishment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    AutoAction,
    DetectionSource,
    IPBlockScope,
    IPBlockStatus,
    RiskLevel,
    SeverityLevel,
    UserStatus,
    ViolationType,
)
from app.models.message import MessageEndpoint
from app.models.security import (
    SecurityIPBlock,
    SecurityIPRiskStats,
    UserRiskStats,
    UserViolationLog,
)
from app.models.user import User, UserToken
from app.services.message.websocket.manager import ws_manager
from app.services.security.attack_detection import AttackMatch, detect_attack_in_fields
from app.services.system_config import get_config
from app.type_defs import JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)

_RULE_VERSION_FALLBACK = "2026-05-02"
_HIGH_RISK_WINDOW_SECONDS_FALLBACK = 300
_MEDIUM_RISK_WINDOW_SECONDS_FALLBACK = 600
_HIGH_RISK_THRESHOLD_FALLBACK = 8
_MEDIUM_RISK_THRESHOLD_FALLBACK = 20
_HIGH_RISK_TTL_FALLBACK = 86400
_MEDIUM_RISK_TTL_FALLBACK = 3600


async def _config_int(db: AsyncSession, key: str, default: int) -> int:
    raw_value = await get_config(db, key, required=False)
    if raw_value is None or isinstance(raw_value, bool):
        return default
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, float) and raw_value.is_integer():
        return int(raw_value)
    if isinstance(raw_value, str):
        try:
            return int(raw_value.strip())
        except ValueError:
            return default
    return default


async def _config_bool(db: AsyncSession, key: str, default: bool) -> bool:
    raw_value = await get_config(db, key, required=False)
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        lowered = raw_value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off", ""}:
            return False
    return default


async def _config_str(db: AsyncSession, key: str, default: str) -> str:
    raw_value = await get_config(db, key, required=False)
    if raw_value is None:
        return default
    if isinstance(raw_value, str):
        value = raw_value.strip()
        return value if value else default
    return str(raw_value).strip() or default


@dataclass(slots=True)
class SecurityRequestContext:
    """Request-level context used by the security enforcement pipeline."""

    detection_source: DetectionSource
    request_method: str
    request_path: str
    client_ip: str
    request_id: str
    user_id: int | None
    user_qiao_id: str | None


def _violation_key(violation_type: ViolationType) -> str:
    mapping: dict[ViolationType, str] = {
        ViolationType.PROMPT_INJECTION: "prompt_injection",
        ViolationType.SQL_INJECTION: "sql_injection",
        ViolationType.COMMAND_INJECTION: "command_injection",
        ViolationType.PATH_TRAVERSAL: "path_traversal",
        ViolationType.OTHER: "other",
    }
    return mapping.get(violation_type, "other")


async def _acquire_user_advisory_lock(db: AsyncSession, *, user_id: int) -> None:
    """Serialize concurrent risk updates for the same user."""
    await db.execute(select(func.pg_advisory_xact_lock(user_id)))


async def _acquire_ip_advisory_lock(db: AsyncSession, *, client_ip: str) -> None:
    """Serialize concurrent risk/block updates for the same source IP."""
    await db.execute(select(func.pg_advisory_xact_lock(31002, func.hashtext(client_ip))))


async def is_ip_blocked(db: AsyncSession, client_ip: str) -> bool:
    """Return whether the client IP currently has an active TTL block."""
    normalized_ip = client_ip.strip()
    if normalized_ip == "":
        return False

    now = datetime.now(UTC)
    result = await db.execute(
        select(SecurityIPBlock.id)
        .where(
            and_(
                SecurityIPBlock.ip_address == normalized_ip,
                SecurityIPBlock.status == int(IPBlockStatus.ACTIVE),
                SecurityIPBlock.expires_at > now,
            )
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def enforce_attack_scan(
    db: AsyncSession,
    *,
    context: SecurityRequestContext,
    fields: dict[str, str],
    extra_evidence: JSONDict | None = None,
) -> AttackMatch | None:
    """Detect attack signatures and execute punishment workflow when matched."""
    attack_match = detect_attack_in_fields(fields)
    if attack_match is None:
        return None

    await _apply_attack_enforcement(
        db,
        context=context,
        attack_match=attack_match,
        extra_evidence=extra_evidence,
    )
    return attack_match


async def _apply_attack_enforcement(
    db: AsyncSession,
    *,
    context: SecurityRequestContext,
    attack_match: AttackMatch,
    extra_evidence: JSONDict | None,
) -> None:
    now = datetime.now(UTC)

    rule_version = await _config_str(db, "security_rule_version", _RULE_VERSION_FALLBACK)

    evidence_payload: JSONDict = {
        "field": attack_match.field_name,
        "evidence": attack_match.evidence,
    }
    if extra_evidence:
        evidence_payload.update(extra_evidence)

    auto_action = AutoAction.NONE
    user_suspended = False

    stats = await _upsert_user_risk_stats(
        db,
        user_id=context.user_id,
        user_qiao_id=context.user_qiao_id,
        violation_type=attack_match.violation_type,
        severity_level=attack_match.severity_level,
        now=now,
    )

    if (
        context.user_id is not None
        and attack_match.severity_level >= SeverityLevel.HIGH
        and await _config_bool(db, "security_user_auto_suspend_enabled", True)
    ):
        user_suspended = await _suspend_user_and_revoke_tokens(
            db,
            user_id=context.user_id,
            stats=stats,
            now=now,
        )
        if user_suspended:
            auto_action = AutoAction.SUSPEND

    violation = UserViolationLog(
        user_id=context.user_id,
        user_qiao_id=context.user_qiao_id,
        instance_id=None,
        instance_qiao_id=None,
        violation_type=int(attack_match.violation_type),
        severity_level=int(attack_match.severity_level),
        original_message=attack_match.evidence,
        auto_action_taken=int(auto_action),
        manual_review_status=1,
        rule_code=attack_match.rule_code,
        rule_version=rule_version,
        detection_source=int(context.detection_source),
        http_method=context.request_method[:16],
        request_path=context.request_path[:255],
        client_ip=context.client_ip or None,
        request_id=(context.request_id or "")[:64] or None,
        evidence_payload=evidence_payload,
        trigger_score=100 if attack_match.severity_level >= SeverityLevel.HIGH else 60,
    )
    db.add(violation)
    # Flush first so IP-window queries can include the current violation hit.
    await db.flush()

    if context.client_ip.strip() != "":
        await _update_ip_risk_and_block(
            db,
            client_ip=context.client_ip.strip(),
            context=context,
            attack_match=attack_match,
            now=now,
            rule_version=rule_version,
            evidence_payload=evidence_payload,
        )

    await db.commit()

    if user_suspended and context.user_id is not None:
        await _disconnect_user_websocket_endpoints(db, user_id=context.user_id)


async def _upsert_user_risk_stats(
    db: AsyncSession,
    *,
    user_id: int | None,
    user_qiao_id: str | None,
    violation_type: ViolationType,
    severity_level: SeverityLevel,
    now: datetime,
) -> UserRiskStats | None:
    if user_id is None or user_qiao_id is None:
        return None

    await _acquire_user_advisory_lock(db, user_id=user_id)

    result = await db.execute(
        select(UserRiskStats).where(UserRiskStats.user_id == user_id).with_for_update()
    )
    stats = result.scalar_one_or_none()
    key = _violation_key(violation_type)

    if stats is None:
        violation_by_type = {key: 1}
        stats = UserRiskStats(
            user_id=user_id,
            user_qiao_id=user_qiao_id,
            total_violations=1,
            violation_by_type=violation_by_type,
            last_violation_at=now,
            consecutive_violations=1,
            high_risk_hits=1 if severity_level >= SeverityLevel.HIGH else 0,
            last_high_risk_at=now if severity_level >= SeverityLevel.HIGH else None,
        )
        db.add(stats)
        return stats

    current_counts = dict(stats.violation_by_type or {})
    raw_value = current_counts.get(key)
    if isinstance(raw_value, int) and not isinstance(raw_value, bool):
        current_counts[key] = raw_value + 1
    else:
        current_counts[key] = 1

    stats.total_violations = int(stats.total_violations) + 1
    stats.user_qiao_id = user_qiao_id
    stats.violation_by_type = current_counts
    stats.last_violation_at = now
    stats.consecutive_violations = int(stats.consecutive_violations) + 1

    if severity_level >= SeverityLevel.HIGH:
        stats.high_risk_hits = int(stats.high_risk_hits) + 1
        stats.last_high_risk_at = now
        stats.current_risk_level = int(RiskLevel.HIGH)

    db.add(stats)
    return stats


async def _suspend_user_and_revoke_tokens(
    db: AsyncSession,
    *,
    user_id: int,
    stats: UserRiskStats | None,
    now: datetime,
) -> bool:
    result = await db.execute(select(User).where(User.id == user_id).with_for_update())
    user = result.scalar_one_or_none()
    if user is None:
        return False

    suspended = False
    if user.status != int(UserStatus.SUSPENDED):
        user.status = int(UserStatus.SUSPENDED)
        db.add(user)
        suspended = True

    token_result = await db.execute(
        select(UserToken).where(
            and_(
                UserToken.user_id == user_id,
                UserToken.status == 1,
            )
        )
    )
    tokens = token_result.scalars().all()
    for token in tokens:
        token.status = 2
        token.access_revoked_at = now
        token.refresh_revoked_at = now
        db.add(token)

    if stats is not None:
        stats.suspension_count = int(stats.suspension_count) + 1
        stats.last_suspend_at = now
        stats.last_action_at = now
        stats.current_risk_level = int(RiskLevel.BANNED)
        db.add(stats)

    return suspended


async def _disconnect_user_websocket_endpoints(db: AsyncSession, *, user_id: int) -> None:
    result = await db.execute(select(MessageEndpoint.id).where(MessageEndpoint.user_id == user_id))
    endpoint_ids = [int(row[0]) for row in result.all()]
    for endpoint_id in endpoint_ids:
        await ws_manager.unregister(endpoint_id)


async def _update_ip_risk_and_block(
    db: AsyncSession,
    *,
    client_ip: str,
    context: SecurityRequestContext,
    attack_match: AttackMatch,
    now: datetime,
    rule_version: str,
    evidence_payload: JSONDict,
) -> None:
    await _acquire_ip_advisory_lock(db, client_ip=client_ip)

    stats_result = await db.execute(
        select(SecurityIPRiskStats)
        .where(SecurityIPRiskStats.ip_address == client_ip)
        .with_for_update()
    )
    stats = stats_result.scalar_one_or_none()

    if stats is None:
        stats = SecurityIPRiskStats(
            ip_address=client_ip,
            high_risk_count_5m=0,
            medium_risk_count_10m=0,
            total_attack_count=0,
        )
        db.add(stats)

    stats.total_attack_count = int(stats.total_attack_count) + 1
    high_window_seconds = await _config_int(
        db,
        "security_ip_high_risk_threshold_window_seconds",
        _HIGH_RISK_WINDOW_SECONDS_FALLBACK,
    )
    medium_window_seconds = await _config_int(
        db,
        "security_ip_medium_risk_threshold_window_seconds",
        _MEDIUM_RISK_WINDOW_SECONDS_FALLBACK,
    )
    stats.high_risk_count_5m = await _count_ip_hits(
        db,
        client_ip=client_ip,
        severity_floor=SeverityLevel.HIGH,
        window_seconds=high_window_seconds,
        now=now,
    )
    stats.medium_risk_count_10m = await _count_ip_hits(
        db,
        client_ip=client_ip,
        severity_floor=SeverityLevel.MEDIUM,
        window_seconds=medium_window_seconds,
        now=now,
    )

    stats.last_attack_at = now
    stats.last_rule_code = attack_match.rule_code
    stats.last_source = context.detection_source.name.lower()
    stats.last_request_path = context.request_path[:255]
    stats.last_user_id = context.user_id
    db.add(stats)

    if await _should_block_ip(db, stats=stats, severity_level=attack_match.severity_level):
        await _upsert_ip_block(
            db,
            stats=stats,
            context=context,
            attack_match=attack_match,
            now=now,
            rule_version=rule_version,
            evidence_payload=evidence_payload,
        )


async def _should_block_ip(
    db: AsyncSession,
    *,
    stats: SecurityIPRiskStats,
    severity_level: SeverityLevel,
) -> bool:
    if severity_level >= SeverityLevel.HIGH:
        high_threshold = await _config_int(
            db,
            "security_ip_high_risk_threshold_count",
            _HIGH_RISK_THRESHOLD_FALLBACK,
        )
        return int(stats.high_risk_count_5m) >= high_threshold

    if severity_level >= SeverityLevel.MEDIUM:
        medium_threshold = await _config_int(
            db,
            "security_ip_medium_risk_threshold_count",
            _MEDIUM_RISK_THRESHOLD_FALLBACK,
        )
        return int(stats.medium_risk_count_10m) >= medium_threshold

    return False


async def _count_ip_hits(
    db: AsyncSession,
    *,
    client_ip: str,
    severity_floor: SeverityLevel,
    window_seconds: int,
    now: datetime,
) -> int:
    if window_seconds <= 0:
        return 0
    window_start = now - timedelta(seconds=window_seconds)
    result = await db.execute(
        select(func.count(UserViolationLog.id)).where(
            and_(
                UserViolationLog.client_ip == client_ip,
                UserViolationLog.created_at >= window_start,
                UserViolationLog.severity_level >= int(severity_floor),
            )
        )
    )
    raw_count = result.scalar_one_or_none()
    return int(raw_count or 0)


async def _upsert_ip_block(
    db: AsyncSession,
    *,
    stats: SecurityIPRiskStats,
    context: SecurityRequestContext,
    attack_match: AttackMatch,
    now: datetime,
    rule_version: str,
    evidence_payload: JSONDict,
) -> None:
    high_ttl_seconds = await _config_int(
        db,
        "security_ip_block_high_ttl_seconds",
        _HIGH_RISK_TTL_FALLBACK,
    )
    medium_ttl_seconds = await _config_int(
        db,
        "security_ip_block_medium_ttl_seconds",
        _MEDIUM_RISK_TTL_FALLBACK,
    )

    ttl_seconds = (
        high_ttl_seconds
        if attack_match.severity_level >= SeverityLevel.HIGH
        else medium_ttl_seconds
    )
    expires_at = now + timedelta(seconds=max(ttl_seconds, 1))

    active_result = await db.execute(
        select(SecurityIPBlock)
        .where(
            and_(
                SecurityIPBlock.ip_address == stats.ip_address,
                SecurityIPBlock.status == int(IPBlockStatus.ACTIVE),
                SecurityIPBlock.expires_at > now,
            )
        )
        .limit(1)
        .with_for_update()
    )
    active_block = active_result.scalar_one_or_none()

    if active_block is not None:
        active_block.hit_count = int(active_block.hit_count) + 1
        active_block.expires_at = expires_at
        active_block.rule_code = attack_match.rule_code
        active_block.rule_version = rule_version
        active_block.source = context.detection_source.name.lower()
        active_block.request_path = context.request_path[:255]
        active_block.request_method = context.request_method[:16]
        active_block.evidence_payload = evidence_payload
        active_block.severity_level = int(attack_match.severity_level)
        db.add(active_block)
        return

    block = SecurityIPBlock(
        ip_address=stats.ip_address,
        block_scope=int(IPBlockScope.SINGLE_IP),
        cidr_prefix=None,
        severity_level=int(attack_match.severity_level),
        reason_code="ip_attack_threshold_exceeded",
        rule_code=attack_match.rule_code,
        rule_version=rule_version,
        source=context.detection_source.name.lower(),
        request_path=context.request_path[:255],
        request_method=context.request_method[:16],
        evidence_payload=evidence_payload,
        hit_count=1,
        first_hit_at=now,
        blocked_at=now,
        expires_at=expires_at,
        status=int(IPBlockStatus.ACTIVE),
    )
    db.add(block)

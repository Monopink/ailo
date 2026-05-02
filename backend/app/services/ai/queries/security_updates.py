"""
Security-related write operations for AI orchestration.

This module provides best-effort persistence helpers used by AI response handling.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AutoAction, ManualReviewStatus, SeverityLevel, ViolationType
from app.models.ai import AIConversationItem
from app.models.security import UserRiskStats, UserViolationLog
from app.utils.logging import get_logger

from .instance_queries import get_user_id_by_qiao_id

logger = get_logger(__name__)

NON_TEXT_PLACEHOLDER = "[Non-text message]"
_CONSECUTIVE_RESET_WINDOW = timedelta(days=7)


def _violation_type_key(violation_type: ViolationType) -> str:
    """
    Convert ViolationType to the JSON key used by user_risk_stats.violation_by_type.

    Keys are stable, lowercase, snake_case, and aligned with ViolationType names.
    """
    mapping: dict[ViolationType, str] = {
        ViolationType.PROMPT_INJECTION: "prompt_injection",
        ViolationType.SQL_INJECTION: "sql_injection",
        ViolationType.COMMAND_INJECTION: "command_injection",
        ViolationType.PATH_TRAVERSAL: "path_traversal",
        ViolationType.OTHER: "other",
    }
    return mapping.get(violation_type, "other")


async def create_attack_detected_violation_log(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    instance_qiao_id: str,
    instance_id: int,
    conversation_item_id: int,
) -> bool:
    """
    Best-effort insert for one attack_detected audit record.

    Fixed values (business decision):
    - violation_type: PROMPT_INJECTION
    - severity_level: LOW
    - auto_action_taken: NONE
    - manual_review_status: PENDING
    - non-text original_message: "[Non-text message]"
    """
    try:
        user_id = await get_user_id_by_qiao_id(db, user_qiao_id)
        if not user_id:
            logger.error("attack_violation_log_user_id_missing", user_qiao_id=user_qiao_id)
            return False

        original_message = await _resolve_original_message(db, conversation_item_id)

        async with db.begin_nested():
            violation_log = UserViolationLog(
                user_id=int(user_id),
                user_qiao_id=user_qiao_id,
                instance_id=int(instance_id),
                instance_qiao_id=instance_qiao_id,
                violation_type=int(ViolationType.PROMPT_INJECTION),
                severity_level=int(SeverityLevel.LOW),
                original_message=original_message,
                auto_action_taken=int(AutoAction.NONE),
                manual_review_status=int(ManualReviewStatus.PENDING),
            )
            db.add(violation_log)
            await db.flush()

        await _best_effort_update_user_risk_stats(
            db,
            user_id=int(user_id),
            user_qiao_id=user_qiao_id,
            violation_type=ViolationType.PROMPT_INJECTION,
        )

        return True

    except Exception as exc:  # pragma: no cover - defensive best-effort logging
        logger.error(
            "attack_violation_log_insert_failed",
            error=str(exc),
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            conversation_item_id=conversation_item_id,
            exc_info=True,
        )
        return False


async def _best_effort_update_user_risk_stats(
    db: AsyncSession,
    *,
    user_id: int,
    user_qiao_id: str,
    violation_type: ViolationType,
) -> bool:
    """
    Best-effort upsert to user_risk_stats when a violation log is created.

    Business decisions:
    - Counters include all detections (PENDING + CONFIRMED); we update at insertion time.
    - Duplicate violation logs may exist and are accepted; stats may double-count.
    - Only summary counters are updated; current_risk_level is not changed here.
    """
    now = datetime.now(UTC)
    key = _violation_type_key(violation_type)

    try:
        async with db.begin_nested():
            result = await db.execute(
                select(UserRiskStats).where(UserRiskStats.user_id == user_id).with_for_update()
            )
            stats = result.scalar_one_or_none()

            if not stats:
                stats = UserRiskStats(
                    user_id=user_id,
                    user_qiao_id=user_qiao_id,
                    total_violations=1,
                    violation_by_type={key: 1},
                    last_violation_at=now,
                    consecutive_violations=1,
                )
                db.add(stats)
                await db.flush()
                return True

            last_violation_at = stats.last_violation_at
            if not last_violation_at or (now - last_violation_at) > _CONSECUTIVE_RESET_WINDOW:
                next_consecutive = 1
            else:
                next_consecutive = int(stats.consecutive_violations) + 1

            current_counts = dict(stats.violation_by_type or {})
            raw_count = current_counts.get(key)
            if isinstance(raw_count, int) and not isinstance(raw_count, bool):
                count = raw_count
            else:
                count = 0
            current_counts[key] = count + 1

            stats.user_qiao_id = user_qiao_id
            stats.total_violations = int(stats.total_violations) + 1
            stats.violation_by_type = current_counts
            stats.last_violation_at = now
            stats.consecutive_violations = next_consecutive

            await db.flush()

        return True

    except IntegrityError as exc:
        logger.error(
            "user_risk_stats_upsert_integrity_error",
            error=str(exc),
            user_id=user_id,
            user_qiao_id=user_qiao_id,
            violation_type=int(violation_type),
            exc_info=True,
        )
        return False

    except Exception as exc:  # pragma: no cover - defensive best-effort logging
        logger.error(
            "user_risk_stats_upsert_failed",
            error=str(exc),
            user_id=user_id,
            user_qiao_id=user_qiao_id,
            violation_type=int(violation_type),
            exc_info=True,
        )
        return False


async def _resolve_original_message(db: AsyncSession, conversation_item_id: int) -> str:
    try:
        result = await db.execute(
            select(AIConversationItem).where(AIConversationItem.id == conversation_item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            return NON_TEXT_PLACEHOLDER
        if (item.message_type or "").lower() != "text":
            return NON_TEXT_PLACEHOLDER
        if item.text_content:
            return item.text_content
        return NON_TEXT_PLACEHOLDER
    except Exception as exc:  # pragma: no cover - defensive best-effort logging
        logger.error(
            "attack_violation_log_original_message_fetch_failed",
            error=str(exc),
            conversation_item_id=conversation_item_id,
            exc_info=True,
        )
        return NON_TEXT_PLACEHOLDER

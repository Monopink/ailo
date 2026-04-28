"""Entitlement service.

Provides entitlement account reads and ledger-based write operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.entitlement import (
    entitlement_reason_code as entitlement_reason_code_crud,
)
from app.crud.entitlement import (
    entitlement_type as entitlement_type_crud,
)
from app.crud.entitlement import (
    user_entitlement_account as entitlement_account_crud,
)
from app.crud.entitlement import (
    user_entitlement_ledger as entitlement_ledger_crud,
)
from app.enums.entitlement import EntitlementSourceType
from app.models.entitlement import UserEntitlementAccount
from app.services.system_config import get_config_int
from app.utils.logging import get_logger

logger = get_logger(__name__)

ENTITLEMENT_AI_CONTACT_LIMIT = "ai_contact_limit"

ENTITLEMENT_SOURCE_SYSTEM_INITIAL = EntitlementSourceType.SYSTEM_INITIAL.value
ENTITLEMENT_SOURCE_INVITE_BIND_INVITEE = EntitlementSourceType.INVITE_BIND_INVITEE.value
ENTITLEMENT_SOURCE_INVITE_BIND_INVITER = EntitlementSourceType.INVITE_BIND_INVITER.value
ENTITLEMENT_SOURCE_CAMPAIGN_ATTRIBUTION = EntitlementSourceType.CAMPAIGN_ATTRIBUTION.value
ENTITLEMENT_SOURCE_REDEEM_CODE_CLAIM = EntitlementSourceType.REDEEM_CODE_CLAIM.value
ENTITLEMENT_SOURCE_CONTACT_AI_SLOT = EntitlementSourceType.CONTACT_AI_SLOT.value
ENTITLEMENT_SOURCE_ADMIN_MANUAL_GRANT = EntitlementSourceType.ADMIN_MANUAL_GRANT.value
ENTITLEMENT_SOURCE_ADMIN_MANUAL_ADJUST = EntitlementSourceType.ADMIN_MANUAL_ADJUST.value
ENTITLEMENT_SOURCE_TYPES = {source_type.value for source_type in EntitlementSourceType}

ENTITLEMENT_ACTION_GRANT = 1
ENTITLEMENT_ACTION_CONSUME = 2
ENTITLEMENT_ACTION_REFUND = 3
ENTITLEMENT_ACTION_ADJUST = 4


@dataclass(frozen=True, slots=True)
class EntitlementAccountState:
    """Current account snapshot after entitlement write."""

    granted_total: int
    used_total: int
    available_total: int
    version: int


@dataclass(frozen=True, slots=True)
class EntitlementWriteResult:
    """Result of one entitlement write attempt."""

    applied: bool
    action_type: int
    delta_granted: int
    delta_used: int
    source_type: str
    reason_code: str | None
    idempotency_key: str
    account: EntitlementAccountState | None


async def _get_entitlement_type_id_or_raise(db: AsyncSession, *, code: str) -> int:
    entitlement_type = await entitlement_type_crud.get_by_code(db, code=code)
    if entitlement_type is None or int(entitlement_type.status) != 1:
        logger.error("entitlement_type_not_found", code=code)
        raise ValueError("Entitlement type not configured")
    return int(entitlement_type.id)


async def _ensure_source_type_or_raise(*, code: str) -> None:
    if code not in ENTITLEMENT_SOURCE_TYPES:
        logger.error("entitlement_source_type_not_found", code=code)
        raise ValueError("Entitlement source type not configured")


async def _ensure_reason_code_active_or_raise(db: AsyncSession, *, code: str) -> None:
    reason_code = await entitlement_reason_code_crud.get_by_code(db, code=code)
    if reason_code is None or int(reason_code.status) != 1:
        logger.error("entitlement_reason_code_not_found", code=code)
        raise ValueError("Entitlement reason code not configured")


async def _ensure_reason_code_for_admin_operation_or_raise(
    db: AsyncSession, *, code: str, operation_type: Literal["grant", "adjust"]
) -> None:
    reason_code = await entitlement_reason_code_crud.get_by_code(db, code=code)
    if reason_code is None or int(reason_code.status) != 1:
        logger.error("entitlement_reason_code_not_found", code=code)
        raise ValueError("Entitlement reason code not configured")

    applies_to = str(getattr(reason_code, "applies_to", "both") or "both").strip().lower()
    if applies_to not in {"grant", "adjust", "both"}:
        logger.error("entitlement_reason_code_applies_to_invalid", code=code, applies_to=applies_to)
        raise ValueError("Entitlement reason code configuration invalid")
    if applies_to not in {"both", operation_type}:
        logger.error(
            "entitlement_reason_code_operation_mismatch",
            code=code,
            applies_to=applies_to,
            operation_type=operation_type,
        )
        raise ValueError("Entitlement reason code does not support this operation type")


def _build_account_state(account: UserEntitlementAccount | None) -> EntitlementAccountState | None:
    if account is None:
        return None
    granted_total = int(account.granted_total)
    used_total = int(account.used_total)
    available_total = int(account.available_total)
    version = int(account.version)
    return EntitlementAccountState(
        granted_total=granted_total,
        used_total=used_total,
        available_total=available_total,
        version=version,
    )


async def _apply_entitlement_delta(
    db: AsyncSession,
    *,
    user_id: int,
    entitlement_type_code: str,
    action_type: int,
    delta_granted: int,
    delta_used: int,
    source_type: str,
    source_id: int,
    idempotency_key: str,
    reason_code: str | None = None,
    operator_admin_user_id: int | None = None,
    effective_at: datetime | None = None,
    event_payload: dict[str, object] | None = None,
) -> EntitlementWriteResult:
    if delta_granted == 0 and delta_used == 0:
        raise ValueError("Entitlement delta cannot be zero")
    if action_type not in (
        ENTITLEMENT_ACTION_GRANT,
        ENTITLEMENT_ACTION_CONSUME,
        ENTITLEMENT_ACTION_REFUND,
        ENTITLEMENT_ACTION_ADJUST,
    ):
        raise ValueError("Invalid entitlement action type")

    entitlement_type_id = await _get_entitlement_type_id_or_raise(db, code=entitlement_type_code)
    await _ensure_source_type_or_raise(code=source_type)
    if reason_code is not None:
        await _ensure_reason_code_active_or_raise(db, code=reason_code)

    existing = await entitlement_ledger_crud.get_by_idempotency_key(
        db,
        user_id=user_id,
        entitlement_type_id=entitlement_type_id,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        account = await entitlement_account_crud.get_by_user_and_type(
            db,
            user_id=user_id,
            entitlement_type_id=entitlement_type_id,
            for_update=False,
        )
        return EntitlementWriteResult(
            applied=False,
            action_type=action_type,
            delta_granted=delta_granted,
            delta_used=delta_used,
            source_type=source_type,
            reason_code=reason_code,
            idempotency_key=idempotency_key,
            account=_build_account_state(account),
        )

    account = await entitlement_account_crud.get_by_user_and_type(
        db,
        user_id=user_id,
        entitlement_type_id=entitlement_type_id,
        for_update=True,
    )
    if account is None:
        account = await entitlement_account_crud.create_account(
            db,
            user_id=user_id,
            entitlement_type_id=entitlement_type_id,
        )

    next_granted_total = int(account.granted_total) + delta_granted
    next_used_total = int(account.used_total) + delta_used
    if next_granted_total < 0:
        raise ValueError("Entitlement granted_total cannot be negative")
    if next_used_total < 0:
        raise ValueError("Entitlement used_total cannot be negative")
    if next_granted_total < next_used_total:
        raise ValueError("Entitlement available_total cannot be negative")

    now = datetime.now(UTC)
    await entitlement_ledger_crud.create_ledger(
        db,
        user_id=user_id,
        entitlement_type_id=entitlement_type_id,
        action_type=action_type,
        delta_granted=delta_granted,
        delta_used=delta_used,
        source_type=source_type,
        source_id=source_id,
        reason_code=reason_code,
        operator_admin_user_id=operator_admin_user_id,
        idempotency_key=idempotency_key,
        effective_at=effective_at or now,
        event_payload=event_payload,
    )

    account.granted_total = next_granted_total
    account.used_total = next_used_total
    account.available_total = next_granted_total - next_used_total
    account.version = int(account.version) + 1
    await db.flush()

    return EntitlementWriteResult(
        applied=True,
        action_type=action_type,
        delta_granted=delta_granted,
        delta_used=delta_used,
        source_type=source_type,
        reason_code=reason_code,
        idempotency_key=idempotency_key,
        account=_build_account_state(account),
    )


async def get_ai_contact_limit(db: AsyncSession, *, user_id: int) -> int:
    entitlement_type_id = await _get_entitlement_type_id_or_raise(
        db, code=ENTITLEMENT_AI_CONTACT_LIMIT
    )
    account = await entitlement_account_crud.get_by_user_and_type(
        db,
        user_id=user_id,
        entitlement_type_id=entitlement_type_id,
    )
    if account is None:
        logger.error("ai_contact_limit_account_missing", user_id=user_id)
        raise ValueError("AI contact limit account missing")
    available_total = int(account.available_total)
    if available_total < 0:
        logger.error("ai_contact_limit_available_invalid", user_id=user_id, value=available_total)
        raise ValueError("AI contact limit account invalid")
    return available_total


async def grant_entitlement(
    db: AsyncSession,
    *,
    user_id: int,
    entitlement_type_code: str,
    value: int,
    source_type: str,
    source_id: int,
    idempotency_key: str,
    reason_code: str | None = None,
    operator_admin_user_id: int | None = None,
    effective_at: datetime | None = None,
    event_payload: dict[str, object] | None = None,
) -> bool:
    if value < 0:
        logger.error(
            "entitlement_grant_value_invalid",
            user_id=user_id,
            entitlement_type_code=entitlement_type_code,
            value=value,
        )
        raise ValueError("Entitlement grant value must be >= 0")

    if value == 0:
        return False

    result = await _apply_entitlement_delta(
        db,
        user_id=user_id,
        entitlement_type_code=entitlement_type_code,
        action_type=ENTITLEMENT_ACTION_GRANT,
        delta_granted=value,
        delta_used=0,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=idempotency_key,
        reason_code=reason_code,
        operator_admin_user_id=operator_admin_user_id,
        effective_at=effective_at,
        event_payload=event_payload,
    )
    return result.applied


async def consume_entitlement(
    db: AsyncSession,
    *,
    user_id: int,
    entitlement_type_code: str,
    value: int,
    source_type: str,
    source_id: int,
    idempotency_key: str,
    reason_code: str | None = None,
    operator_admin_user_id: int | None = None,
    effective_at: datetime | None = None,
    event_payload: dict[str, object] | None = None,
) -> bool:
    if value < 0:
        logger.error(
            "entitlement_consume_value_invalid",
            user_id=user_id,
            entitlement_type_code=entitlement_type_code,
            value=value,
        )
        raise ValueError("Entitlement consume value must be >= 0")
    if value == 0:
        return False
    result = await _apply_entitlement_delta(
        db,
        user_id=user_id,
        entitlement_type_code=entitlement_type_code,
        action_type=ENTITLEMENT_ACTION_CONSUME,
        delta_granted=0,
        delta_used=value,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=idempotency_key,
        reason_code=reason_code,
        operator_admin_user_id=operator_admin_user_id,
        effective_at=effective_at,
        event_payload=event_payload,
    )
    return result.applied


async def refund_entitlement(
    db: AsyncSession,
    *,
    user_id: int,
    entitlement_type_code: str,
    value: int,
    source_type: str,
    source_id: int,
    idempotency_key: str,
    reason_code: str | None = None,
    operator_admin_user_id: int | None = None,
    effective_at: datetime | None = None,
    event_payload: dict[str, object] | None = None,
) -> bool:
    if value < 0:
        logger.error(
            "entitlement_refund_value_invalid",
            user_id=user_id,
            entitlement_type_code=entitlement_type_code,
            value=value,
        )
        raise ValueError("Entitlement refund value must be >= 0")
    if value == 0:
        return False
    result = await _apply_entitlement_delta(
        db,
        user_id=user_id,
        entitlement_type_code=entitlement_type_code,
        action_type=ENTITLEMENT_ACTION_REFUND,
        delta_granted=0,
        delta_used=-value,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=idempotency_key,
        reason_code=reason_code,
        operator_admin_user_id=operator_admin_user_id,
        effective_at=effective_at,
        event_payload=event_payload,
    )
    return result.applied


async def admin_operate_entitlement(
    db: AsyncSession,
    *,
    admin_user_id: int,
    user_id: int,
    entitlement_type_code: str,
    operation_type: Literal["grant", "adjust"],
    delta: int,
    reason_code: str,
    idempotency_key: str,
    remark: str | None,
) -> EntitlementWriteResult:
    await _ensure_reason_code_for_admin_operation_or_raise(
        db, code=reason_code, operation_type=operation_type
    )

    if operation_type == "grant":
        if delta <= 0:
            raise ValueError("Admin grant delta must be > 0")
        action_type = ENTITLEMENT_ACTION_GRANT
        source_type = ENTITLEMENT_SOURCE_ADMIN_MANUAL_GRANT
    else:
        if delta == 0:
            raise ValueError("Admin adjust delta must not be 0")
        action_type = ENTITLEMENT_ACTION_ADJUST
        source_type = ENTITLEMENT_SOURCE_ADMIN_MANUAL_ADJUST

    payload: dict[str, object] = {
        "operation_type": operation_type,
        "admin_user_id": admin_user_id,
    }
    if isinstance(remark, str) and remark.strip() != "":
        payload["remark"] = remark.strip()
    return await _apply_entitlement_delta(
        db,
        user_id=user_id,
        entitlement_type_code=entitlement_type_code,
        action_type=action_type,
        delta_granted=delta,
        delta_used=0,
        source_type=source_type,
        source_id=admin_user_id,
        reason_code=reason_code,
        operator_admin_user_id=admin_user_id,
        idempotency_key=idempotency_key,
        effective_at=datetime.now(UTC),
        event_payload=payload,
    )


async def ensure_system_initial_ai_contact_limit(db: AsyncSession, *, user_id: int) -> None:
    initial_limit = await get_config_int(db, key="contacts_initial_ai_contact_limit")
    if initial_limit < 1:
        logger.error("contacts_initial_ai_contact_limit_invalid", value=initial_limit)
        raise ValueError("contacts_initial_ai_contact_limit invalid")

    await grant_entitlement(
        db,
        user_id=user_id,
        entitlement_type_code=ENTITLEMENT_AI_CONTACT_LIMIT,
        value=initial_limit,
        source_type=ENTITLEMENT_SOURCE_SYSTEM_INITIAL,
        source_id=0,
        idempotency_key="system_initial:0",
    )

"""Entitlement CRUD operations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entitlement import (
    EntitlementReasonCode,
    EntitlementType,
    UserEntitlementAccount,
    UserEntitlementLedger,
)


class CRUDEntitlementType:
    """CRUD helpers for entitlement_types."""

    async def get_by_code(self, db: AsyncSession, *, code: str) -> EntitlementType | None:
        """Return entitlement type row by unique code."""
        result = await db.execute(select(EntitlementType).where(EntitlementType.code == code))
        return result.scalar_one_or_none()


class CRUDEntitlementReasonCode:
    """CRUD helpers for entitlement_reason_codes."""

    async def get_by_code(self, db: AsyncSession, *, code: str) -> EntitlementReasonCode | None:
        """Return reason code row by unique code."""
        result = await db.execute(
            select(EntitlementReasonCode).where(EntitlementReasonCode.code == code)
        )
        return result.scalar_one_or_none()


class CRUDUserEntitlementAccount:
    """CRUD helpers for user_entitlement_accounts."""

    async def get_by_user_and_type(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_type_id: int,
        for_update: bool = False,
    ) -> UserEntitlementAccount | None:
        """Return account row by user/type, with optional row lock."""
        stmt = select(UserEntitlementAccount).where(
            UserEntitlementAccount.user_id == user_id,
            UserEntitlementAccount.entitlement_type_id == entitlement_type_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_account(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_type_id: int,
    ) -> UserEntitlementAccount:
        """Create empty account snapshot row for a user/type pair."""
        obj = UserEntitlementAccount(
            user_id=user_id,
            entitlement_type_id=entitlement_type_id,
            granted_total=0,
            used_total=0,
            available_total=0,
            version=0,
        )
        db.add(obj)
        await db.flush()
        return obj


class CRUDUserEntitlementLedger:
    """CRUD helpers for user_entitlement_ledger."""

    async def get_by_idempotency_key(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_type_id: int,
        idempotency_key: str,
    ) -> UserEntitlementLedger | None:
        """Return ledger row by unique idempotency key scope."""
        result = await db.execute(
            select(UserEntitlementLedger).where(
                UserEntitlementLedger.user_id == user_id,
                UserEntitlementLedger.entitlement_type_id == entitlement_type_id,
                UserEntitlementLedger.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def create_ledger(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_type_id: int,
        action_type: int,
        delta_granted: int,
        delta_used: int,
        source_type: str,
        source_id: int,
        reason_code: str | None,
        operator_admin_user_id: int | None,
        idempotency_key: str,
        effective_at: datetime,
        event_payload: dict[str, object] | None,
    ) -> UserEntitlementLedger:
        """Insert one immutable ledger record."""
        obj = UserEntitlementLedger(
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
            effective_at=effective_at,
            event_payload=event_payload,
        )
        db.add(obj)
        await db.flush()
        return obj


entitlement_type = CRUDEntitlementType()
entitlement_reason_code = CRUDEntitlementReasonCode()
user_entitlement_account = CRUDUserEntitlementAccount()
user_entitlement_ledger = CRUDUserEntitlementLedger()

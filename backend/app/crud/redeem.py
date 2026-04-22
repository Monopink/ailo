"""Redeem code related CRUD operations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.redeem import RedeemCodeStatus
from app.models.redeem import RedeemCode, RedeemCodeBatch, RedeemCodeClaim


class CRUDRedeemCodeBatch:
    """CRUD helpers for redeem_code_batches."""

    async def get_by_id(
        self, db: AsyncSession, *, batch_id: int, for_update: bool = False
    ) -> RedeemCodeBatch | None:
        """Return redeem batch by id."""
        stmt = select(RedeemCodeBatch).where(RedeemCodeBatch.id == batch_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


class CRUDRedeemCode:
    """CRUD helpers for redeem_codes."""

    async def get_active_by_code(
        self,
        db: AsyncSession,
        *,
        code: str,
        at: datetime | None = None,
        for_update: bool = False,
    ) -> RedeemCode | None:
        """Return active redeem code by code value and time."""
        now = at or datetime.now(UTC)
        stmt = select(RedeemCode).where(
            RedeemCode.code == code,
            RedeemCode.status == int(RedeemCodeStatus.ACTIVE),
            (RedeemCode.starts_at.is_(None) | (RedeemCode.starts_at <= now)),
            (RedeemCode.ends_at.is_(None) | (RedeemCode.ends_at > now)),
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


class CRUDRedeemCodeClaim:
    """CRUD helpers for redeem_code_claims."""

    async def get_by_user_and_code(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        redeem_code_id: int,
    ) -> RedeemCodeClaim | None:
        """Return one claim by user id and redeem code id."""
        result = await db.execute(
            select(RedeemCodeClaim).where(
                RedeemCodeClaim.user_id == user_id,
                RedeemCodeClaim.redeem_code_id == redeem_code_id,
            )
        )
        return result.scalar_one_or_none()

    async def count_by_user_and_batch(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        batch_id: int,
    ) -> int:
        """Count how many claims the user has in one batch."""
        result = await db.execute(
            select(func.count())
            .select_from(RedeemCodeClaim)
            .where(RedeemCodeClaim.user_id == user_id, RedeemCodeClaim.batch_id == batch_id)
        )
        value = result.scalar_one()
        return int(value) if isinstance(value, int) else int(value or 0)

    async def create_claim(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        redeem_code_id: int,
        batch_id: int,
        code_snapshot: str,
        idempotency_key: str,
        event_payload: dict[str, object] | None,
    ) -> RedeemCodeClaim:
        """Create one redeem claim row."""
        obj = RedeemCodeClaim(
            user_id=user_id,
            redeem_code_id=redeem_code_id,
            batch_id=batch_id,
            code_snapshot=code_snapshot,
            idempotency_key=idempotency_key,
            event_payload=event_payload,
        )
        db.add(obj)
        await db.flush()
        return obj


redeem_code_batch = CRUDRedeemCodeBatch()
redeem_code = CRUDRedeemCode()
redeem_code_claim = CRUDRedeemCodeClaim()

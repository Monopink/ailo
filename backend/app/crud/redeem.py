"""Redeem code related CRUD operations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.redeem import RedeemCodeStatus
from app.models.redeem import RedeemBatchUserCounter, RedeemCode, RedeemCodeBatch, RedeemCodeClaim


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

    async def increment_budget_used_if_available(
        self,
        db: AsyncSession,
        *,
        batch_id: int,
        at: datetime,
    ) -> bool:
        """Atomically increment batch budget usage when budget is available."""
        stmt = (
            update(RedeemCodeBatch)
            .where(
                RedeemCodeBatch.id == batch_id,
                RedeemCodeBatch.status == 1,
                or_(RedeemCodeBatch.starts_at.is_(None), RedeemCodeBatch.starts_at <= at),
                or_(RedeemCodeBatch.ends_at.is_(None), RedeemCodeBatch.ends_at > at),
                or_(
                    RedeemCodeBatch.budget_total.is_(None),
                    RedeemCodeBatch.budget_used < RedeemCodeBatch.budget_total,
                ),
            )
            .values(budget_used=RedeemCodeBatch.budget_used + 1)
        )
        result = await db.execute(stmt)
        return int(result.rowcount or 0) > 0


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

    async def increment_claimed_total_if_available(
        self,
        db: AsyncSession,
        *,
        redeem_code_id: int,
        at: datetime,
        max_claims_total: int | None,
        enforce_one_time: bool,
    ) -> bool:
        """Atomically increment redeem code claimed_total when quota allows."""
        conditions = [
            RedeemCode.id == redeem_code_id,
            RedeemCode.status == int(RedeemCodeStatus.ACTIVE),
            or_(RedeemCode.starts_at.is_(None), RedeemCode.starts_at <= at),
            or_(RedeemCode.ends_at.is_(None), RedeemCode.ends_at > at),
        ]
        if max_claims_total is not None:
            conditions.append(RedeemCode.claimed_total < max_claims_total)
        if enforce_one_time:
            conditions.append(RedeemCode.claimed_total < 1)

        stmt = (
            update(RedeemCode)
            .where(and_(*conditions))
            .values(claimed_total=RedeemCode.claimed_total + 1)
        )
        result = await db.execute(stmt)
        return int(result.rowcount or 0) > 0


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


class CRUDRedeemBatchUserCounter:
    """CRUD helpers for redeem_batch_user_counters."""

    async def increment_with_cap(
        self,
        db: AsyncSession,
        *,
        batch_id: int,
        user_id: int,
        max_claims_per_user: int,
    ) -> int | None:
        """Atomically increment per-user counter with one-batch cap guard."""
        stmt = (
            insert(RedeemBatchUserCounter)
            .values(batch_id=batch_id, user_id=user_id, claimed_total=1)
            .on_conflict_do_update(
                index_elements=[RedeemBatchUserCounter.batch_id, RedeemBatchUserCounter.user_id],
                set_={"claimed_total": RedeemBatchUserCounter.claimed_total + 1},
                where=(RedeemBatchUserCounter.claimed_total < max_claims_per_user),
            )
            .returning(RedeemBatchUserCounter.claimed_total)
        )
        result = await db.execute(stmt)
        value = result.scalar_one_or_none()
        return int(value) if value is not None else None


redeem_code_batch = CRUDRedeemCodeBatch()
redeem_code = CRUDRedeemCode()
redeem_code_claim = CRUDRedeemCodeClaim()
redeem_batch_user_counter = CRUDRedeemBatchUserCounter()

"""Shared helpers for message delivery records."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MessageDeliveryStatus
from app.models.message import MessageDelivery, MessageEndpoint
from app.utils.snowflake import generate_snowflake_id


def _now_utc() -> datetime:
    return datetime.now(UTC)


async def get_delivery(
    db: AsyncSession,
    *,
    msg_id_server: str,
    endpoint_id: int,
) -> MessageDelivery | None:
    result = await db.execute(
        select(MessageDelivery).where(
            MessageDelivery.msg_id_server == msg_id_server,
            MessageDelivery.endpoint_id == endpoint_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_delivery(
    db: AsyncSession,
    *,
    msg_id_server: str,
    endpoint: MessageEndpoint,
    status: MessageDeliveryStatus,
    provider_msg_id: str | None,
    failed_reason_code: str | None,
    failed_detail: str | None,
) -> None:
    now = _now_utc()
    try:
        async with db.begin_nested():
            db.add(
                MessageDelivery(
                    id=generate_snowflake_id(),
                    msg_id_server=msg_id_server,
                    endpoint_id=endpoint.id,
                    provider=endpoint.provider,
                    target_key=endpoint.target_key,
                    provider_msg_id=provider_msg_id,
                    status=status,
                    dispatched_at=now if status == MessageDeliveryStatus.DISPATCHED else None,
                    failed_reason_code=failed_reason_code,
                    failed_detail=failed_detail,
                )
            )
            await db.flush()
            return
    except IntegrityError:
        pass

    existing = await get_delivery(db, msg_id_server=msg_id_server, endpoint_id=endpoint.id)
    if existing is None:
        return
    existing.provider = endpoint.provider
    existing.target_key = endpoint.target_key
    existing.provider_msg_id = provider_msg_id
    existing.status = status
    existing.dispatched_at = now if status == MessageDeliveryStatus.DISPATCHED else None
    existing.failed_reason_code = failed_reason_code
    existing.failed_detail = failed_detail
    db.add(existing)
    await db.flush()

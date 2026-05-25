"""Persistence helpers for security IP blocks."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, cast, select
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import IPBlockStatus
from app.models.security import SecurityIPBlock


async def has_active_block_for_ip(
    db: AsyncSession,
    *,
    normalized_ip: str,
    now: datetime,
) -> bool:
    """Return whether an active block contains the given client IP."""
    result = await db.execute(
        select(SecurityIPBlock.id)
        .where(
            and_(
                SecurityIPBlock.status == int(IPBlockStatus.ACTIVE),
                SecurityIPBlock.expires_at > now,
                cast(normalized_ip, INET).bool_op("<<=")(SecurityIPBlock.target_network),
            )
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def find_active_block_by_target_network(
    db: AsyncSession,
    *,
    target_network: str,
    now: datetime,
    for_update: bool = False,
) -> SecurityIPBlock | None:
    """Find one active block row for an exact target network."""
    statement = (
        select(SecurityIPBlock)
        .where(
            and_(
                SecurityIPBlock.target_network == target_network,
                SecurityIPBlock.status == int(IPBlockStatus.ACTIVE),
                SecurityIPBlock.expires_at > now,
            )
        )
        .limit(1)
    )
    if for_update:
        statement = statement.with_for_update()
    result = await db.execute(statement)
    return result.scalar_one_or_none()

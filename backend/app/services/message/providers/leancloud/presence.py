"""LeanCloud USER endpoint presence registration/renewal."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import MessageEndpoint
from app.services.message.presence import upsert_leancloud_presence_endpoint


async def upsert_user_presence_endpoint(
    db: AsyncSession,
    *,
    user_id: int,
    user_qiao_id: str,
    client_id: str,
    lease_ttl_days: int,
    client_kind: int | None = None,
) -> MessageEndpoint:
    """Create or renew LeanCloud USER-scope endpoint for one user."""
    return await upsert_leancloud_presence_endpoint(
        db,
        user_id=user_id,
        user_qiao_id=user_qiao_id,
        client_id=client_id,
        lease_ttl_days=lease_ttl_days,
        client_kind=client_kind,
    )


__all__ = ["upsert_user_presence_endpoint"]

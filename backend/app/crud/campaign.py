"""Campaign related CRUD operations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.campaign import CampaignStatus
from app.models.campaign import Campaign, CampaignAttribution


class CRUDCampaign:
    """CRUD helpers for campaigns."""

    async def get_active_by_code(
        self,
        db: AsyncSession,
        *,
        campaign_code: str,
        at: datetime | None = None,
        for_update: bool = False,
    ) -> Campaign | None:
        """Return active campaign by campaign code at given time."""
        now = at or datetime.now(UTC)
        stmt = select(Campaign).where(
            Campaign.code == campaign_code,
            Campaign.status == int(CampaignStatus.ACTIVE),
            (Campaign.starts_at.is_(None) | (Campaign.starts_at <= now)),
            (Campaign.ends_at.is_(None) | (Campaign.ends_at > now)),
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


class CRUDCampaignAttribution:
    """CRUD helpers for campaign_attributions."""

    async def get_by_user_id(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        for_update: bool = False,
    ) -> CampaignAttribution | None:
        """Return first-touch attribution row for the user."""
        stmt = select(CampaignAttribution).where(CampaignAttribution.user_id == user_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_attribution(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        campaign_id: int,
        attribution_source: str,
        attributed_at: datetime,
        event_payload: dict[str, object] | None,
    ) -> CampaignAttribution:
        """Create one attribution record."""
        obj = CampaignAttribution(
            user_id=user_id,
            campaign_id=campaign_id,
            attribution_source=attribution_source,
            attributed_at=attributed_at,
            event_payload=event_payload,
        )
        db.add(obj)
        await db.flush()
        return obj


campaign = CRUDCampaign()
campaign_attribution = CRUDCampaignAttribution()

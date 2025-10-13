"""
Preset asset CRUD operations.

This module provides CRUD operations for preset assets (avatars, emoticons, etc.).
"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.system import PresetAsset
from schemas.system import PresetAssetCreate, PresetAssetUpdate


class CRUDPresetAsset(CRUDBase[PresetAsset, PresetAssetCreate, PresetAssetUpdate]):
    """CRUD operations for preset assets."""

    async def get_by_name(self, db: AsyncSession, *, name: str) -> Optional[PresetAsset]:
        """Get preset asset by name."""
        result = await db.execute(select(PresetAsset).where(PresetAsset.name == name))
        return result.scalar_one_or_none()

    async def get_by_type(
        self, db: AsyncSession, *, asset_type: int, skip: int = 0, limit: int = 100
    ) -> List[PresetAsset]:
        """Get preset assets by type."""
        result = await db.execute(
            select(PresetAsset)
            .where(PresetAsset.asset_type == asset_type)
            .where(PresetAsset.status == 1)
            .order_by(PresetAsset.sort_order, PresetAsset.id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_category(
        self,
        db: AsyncSession,
        *,
        asset_type: int,
        category: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[PresetAsset]:
        """Get preset assets by type and category."""
        result = await db.execute(
            select(PresetAsset)
            .where(PresetAsset.asset_type == asset_type)
            .where(PresetAsset.category == category)
            .where(PresetAsset.status == 1)
            .order_by(PresetAsset.sort_order, PresetAsset.id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_client_presets(
        self, db: AsyncSession, *, asset_type: int, skip: int = 0, limit: int = 100
    ) -> List[PresetAsset]:
        """Get client preset assets (bundled with client)."""
        result = await db.execute(
            select(PresetAsset)
            .where(PresetAsset.asset_type == asset_type)
            .where(PresetAsset.is_client_preset == 1)
            .where(PresetAsset.status == 1)
            .order_by(PresetAsset.sort_order, PresetAsset.id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())


# Create instance
preset_assets = CRUDPresetAsset(PresetAsset)

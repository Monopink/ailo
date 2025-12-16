"""
Media file CRUD operations.

This module contains CRUD operations for media file management.
"""

from pydantic import BaseModel
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.enums import FileStatus
from app.models.message import MediaFile
from app.schemas.message import MediaFileUpload


class _MediaFileUpdateSchema(BaseModel):
    """
    Dummy schema for MediaFile update operations.

    MediaFile updates are rare (mostly status changes handled separately),
    so a full update schema is not needed.
    """


class CRUDMediaFile(CRUDBase[MediaFile, MediaFileUpload, _MediaFileUpdateSchema]):
    """CRUD operations for MediaFile model."""

    async def get_by_file_id(self, db: AsyncSession, *, file_id: str) -> MediaFile | None:
        """Get media file by file ID."""
        result = await db.execute(select(self.model).where(self.model.file_id == file_id))
        return result.scalar_one_or_none()

    async def get_user_files(
        self,
        db: AsyncSession,
        *,
        user_qiao_id: str,
        file_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[MediaFile]:
        """Get user's uploaded files."""
        conditions = [self.model.upload_by_qiao_id == user_qiao_id]
        if file_type:
            conditions.append(self.model.file_type == file_type)

        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_file_status(
        self, db: AsyncSession, *, file_id: str, status: FileStatus
    ) -> MediaFile | None:
        """Update file status."""
        file = await self.get_by_file_id(db, file_id=file_id)
        if file:
            file.status = status
            db.add(file)
            await db.commit()
            await db.refresh(file)
        return file


# Create instance
media_file = CRUDMediaFile(MediaFile)

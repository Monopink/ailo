"""Media file CRUD operations.

This module contains CRUD operations for media file management.
"""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.enums import FileStatus, FileType
from app.models.message import MediaFile
from app.schemas.message import MediaFileUpload


class _MediaFileUpdateSchema(BaseModel):
    """Dummy schema for MediaFile update operations.

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

    async def find_active_duplicate(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        file_type: FileType,
        file_hash: str,
        exclude_file_id: int | None = None,
    ) -> MediaFile | None:
        """Find active file with same hash for user."""
        query = (
            select(self.model)
            .where(
                self.model.upload_by_id == user_id,
                self.model.file_type == int(file_type),
                self.model.file_hash == file_hash,
                self.model.status == int(FileStatus.ACTIVE),
            )
            .order_by(self.model.created_at.desc())
        )

        if exclude_file_id:
            query = query.where(self.model.id != exclude_file_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_daily_usage(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        file_type: FileType,
        day_start: datetime | None = None,
    ) -> tuple[int, int]:
        """Return (count, total_bytes) for uploads since day_start."""
        if day_start is None:
            day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        result = await db.execute(
            select(
                func.count(self.model.id),
                func.coalesce(func.sum(self.model.file_size), 0),
            ).where(
                self.model.upload_by_id == user_id,
                self.model.file_type == int(file_type),
                self.model.created_at >= day_start,
                self.model.status != int(FileStatus.DELETED),
            )
        )
        count, total_size = result.one()
        return int(count), int(total_size or 0)


# Create instance
media_file = CRUDMediaFile(MediaFile)

"""Base CRUD operations.

This module contains generic CRUD classes that provide common database operations
for all models.
"""

from typing import Any

from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.protocols import (
    IdModelProtocol,
    ImmutableModelProtocol,
    QiaoIdModelProtocol,
    StatusModelProtocol,
)


class CRUDBase[
    ModelType: IdModelProtocol,
    CreateSchemaType: BaseModel,
    UpdateSchemaType: BaseModel,
]:
    """Base CRUD class with default methods to Create, Read, Update, Delete (CRUD).

    **Parameters**
    * `model`: A SQLAlchemy model class
    * `schema`: A Pydantic model (schema) class
    """

    def __init__(self, model: type[ModelType]) -> None:
        """CRUD object with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**
        * `model`: A SQLAlchemy model class
        """
        self.model = model

    async def get(self, db: AsyncSession, record_id: object) -> ModelType | None:
        """Get a single record by ID."""
        result = await db.execute(select(self.model).where(self.model.id == record_id))
        return result.scalar_one_or_none()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Get multiple records with pagination."""
        result = await db.execute(select(self.model).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record."""
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: ModelType, obj_in: UpdateSchemaType | dict[str, Any]
    ) -> ModelType:
        """Update an existing record."""
        obj_data = db_obj.__dict__
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, record_id: object) -> ModelType | None:
        """Remove a record by ID."""
        obj = await self.get(db, record_id=record_id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

    async def count(self, db: AsyncSession) -> int:
        """Count total records."""
        result = await db.execute(select(func.count(self.model.id)))
        count = result.scalar()
        return count if count is not None else 0

    async def exists(self, db: AsyncSession, *, record_id: object) -> bool:
        """Check if a record exists by ID."""
        result = await db.execute(
            select(func.count(self.model.id)).where(self.model.id == record_id)
        )
        count = result.scalar()
        return (count if count is not None else 0) > 0


class CRUDBaseWithQiaoId[
    ModelType: QiaoIdModelProtocol,
    CreateSchemaType: BaseModel,
    UpdateSchemaType: BaseModel,
](CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]):
    """CRUD base class for models with qiao_id field.

    Extends CRUDBase with qiao_id specific operations.
    """

    async def get_by_qiao_id(self, db: AsyncSession, *, qiao_id: str) -> ModelType | None:
        """Get a single record by qiao_id."""
        result = await db.execute(select(self.model).where(self.model.qiao_id == qiao_id))
        return result.scalar_one_or_none()

    async def exists_by_qiao_id(self, db: AsyncSession, *, qiao_id: str) -> bool:
        """Check if a record exists by qiao_id."""
        result = await db.execute(
            select(func.count(self.model.id)).where(self.model.qiao_id == qiao_id)
        )
        count = result.scalar()
        return (count if count is not None else 0) > 0

    async def get_multi_by_qiao_ids(
        self, db: AsyncSession, *, qiao_ids: list[str]
    ) -> list[ModelType]:
        """Get multiple records by qiao_ids."""
        result = await db.execute(select(self.model).where(self.model.qiao_id.in_(qiao_ids)))
        return list(result.scalars().all())


class CRUDBaseWithStatus[
    ModelType: StatusModelProtocol,
    CreateSchemaType: BaseModel,
    UpdateSchemaType: BaseModel,
](CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]):
    """CRUD base class for models with status field.

    Extends CRUDBase with status-specific operations.
    """

    async def get_active(self, db: AsyncSession, record_id: object) -> ModelType | None:
        """Get a single active record by ID."""
        result = await db.execute(
            select(self.model).where(
                self.model.id == record_id, self.model.status == 1
            )  # Assuming 1 = active
        )
        return result.scalar_one_or_none()

    async def get_multi_active(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Get multiple active records with pagination."""
        result = await db.execute(
            select(self.model).where(self.model.status == 1).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self, db: AsyncSession, *, record_id: object, status: int
    ) -> ModelType | None:
        """Update record status."""
        obj = await self.get(db, record_id=record_id)
        if obj:
            obj.status = status
            db.add(obj)
            await db.commit()
            await db.refresh(obj)
        return obj

    async def soft_delete(self, db: AsyncSession, *, record_id: object) -> ModelType | None:
        """Soft delete a record by setting status to 0."""
        return await self.update_status(db, record_id=record_id, status=0)


class ImmutableCRUDBase[ModelType: ImmutableModelProtocol, CreateSchemaType: BaseModel]:
    """Base CRUD class for immutable log tables.

    Provides only Create and Read operations. No Update or Delete operations.
    Use this for log tables that should never be modified after creation.

    **Parameters**
    * `model`: A SQLAlchemy model class (immutable log table)
    """

    def __init__(self, model: type[ModelType]) -> None:
        """CRUD object for immutable log tables.

        **Parameters**
        * `model`: A SQLAlchemy model class
        """
        self.model = model

    async def get(self, db: AsyncSession, record_id: object) -> ModelType | None:
        """Get a single log record by ID."""
        result = await db.execute(select(self.model).where(self.model.id == record_id))
        return result.scalar_one_or_none()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Get multiple log records with pagination, ordered by created_at DESC."""
        result = await db.execute(
            select(self.model).order_by(desc(self.model.created_at)).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """Create a new log record."""
        obj_in_data = obj_in.model_dump() if hasattr(obj_in, "model_dump") else obj_in.dict()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def count(self, db: AsyncSession) -> int:
        """Count total number of log records."""
        result = await db.execute(select(func.count()).select_from(self.model))
        return result.scalar_one()

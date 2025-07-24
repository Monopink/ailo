from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.ext.declarative import DeclarativeMeta

from utils.logging import get_logger

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=DeclarativeMeta)


class CRUDBase(Generic[ModelType]):
    """Base class for CRUD operations."""

    def __init__(self, model: Type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**
        * `model`: A SQLAlchemy model class
        """
        self.model = model

    async def get(self, db: AsyncSession, id: int) -> Optional[ModelType]:
        """Get a single record by ID."""
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_multi(self, db: AsyncSession, *, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Get multiple records with pagination."""
        result = await db.execute(select(self.model).offset(skip).limit(limit))
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: Dict[str, Any]) -> ModelType:
        """Create a new record."""
        if not obj_in:
            raise ValueError("obj_in cannot be empty")

        try:
            # Filter valid fields for the model
            valid_fields = {key: value for key, value in obj_in.items() if hasattr(self.model, key)}

            db_obj = self.model(**valid_fields)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj

        except Exception as e:
            await db.rollback()
            logger.error("record_creation_failed", model=self.model.__name__, error=str(e))
            raise

    async def update(self, db: AsyncSession, *, db_obj: ModelType, obj_in: Dict[str, Any]) -> ModelType:
        """Update an existing record."""
        if not obj_in:
            raise ValueError("obj_in cannot be empty")

        if not db_obj:
            raise ValueError("db_obj cannot be None")

        try:
            # Update only valid fields
            for field, value in obj_in.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)

            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj

        except Exception as e:
            await db.rollback()
            logger.error("record_update_failed", model=self.model.__name__, error=str(e))
            raise

    async def remove(self, db: AsyncSession, *, id: int) -> Optional[ModelType]:
        """Remove a record by ID."""
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

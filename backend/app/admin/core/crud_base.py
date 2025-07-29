"""
Simple CRUD base class for admin module.
Provides basic database operations for admin models.
"""

from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from admin.models.base import AdminBaseModel
from utils.logging import get_logger

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=AdminBaseModel)


class AdminCRUDBase(Generic[ModelType]):
    """Simple CRUD base class for admin models"""

    def __init__(self, model: Type[ModelType]):
        """
        Initialize CRUD with model class.
        
        Args:
            model: SQLAlchemy model class
        """
        self.model = model

    async def get(self, db: AsyncSession, id: int) -> Optional[ModelType]:
        """Get a single record by ID"""
        try:
            result = await db.execute(select(self.model).where(self.model.id == id))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("get_record_error", model=self.model.__name__, id=id, error=str(e))
            raise

    async def get_multi(
        self, 
        db: AsyncSession, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """Get multiple records with pagination and optional filters"""
        try:
            query = select(self.model)
            
            # Apply filters if provided
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field) and value is not None:
                        query = query.where(getattr(self.model, field) == value)
            
            query = query.offset(skip).limit(limit)
            result = await db.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error("get_multi_error", model=self.model.__name__, error=str(e))
            raise

    async def count(self, db: AsyncSession, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filters"""
        try:
            query = select(func.count(self.model.id))
            
            # Apply filters if provided
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field) and value is not None:
                        query = query.where(getattr(self.model, field) == value)
            
            result = await db.execute(query)
            return result.scalar()
        except Exception as e:
            logger.error("count_error", model=self.model.__name__, error=str(e))
            raise

    async def create(self, db: AsyncSession, *, obj_in: Dict[str, Any]) -> ModelType:
        """Create a new record"""
        try:
            # Filter only valid fields for the model
            valid_fields = {
                key: value for key, value in obj_in.items() 
                if hasattr(self.model, key)
            }
            
            db_obj = self.model(**valid_fields)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            
            logger.info("record_created", model=self.model.__name__, id=db_obj.id)
            return db_obj
        except IntegrityError as e:
            await db.rollback()
            logger.error("create_integrity_error", model=self.model.__name__, error=str(e))
            raise
        except Exception as e:
            await db.rollback()
            logger.error("create_error", model=self.model.__name__, error=str(e))
            raise

    async def update(
        self, 
        db: AsyncSession, 
        *, 
        db_obj: ModelType, 
        obj_in: Dict[str, Any]
    ) -> ModelType:
        """Update an existing record"""
        try:
            # Update only valid fields
            for field, value in obj_in.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)

            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            
            logger.info("record_updated", model=self.model.__name__, id=db_obj.id)
            return db_obj
        except IntegrityError as e:
            await db.rollback()
            logger.error("update_integrity_error", model=self.model.__name__, error=str(e))
            raise
        except Exception as e:
            await db.rollback()
            logger.error("update_error", model=self.model.__name__, error=str(e))
            raise

    async def delete(self, db: AsyncSession, *, id: int) -> Optional[ModelType]:
        """Delete a record by ID"""
        try:
            obj = await self.get(db, id)
            if obj:
                await db.delete(obj)
                await db.commit()
                logger.info("record_deleted", model=self.model.__name__, id=id)
            return obj
        except Exception as e:
            await db.rollback()
            logger.error("delete_error", model=self.model.__name__, id=id, error=str(e))
            raise

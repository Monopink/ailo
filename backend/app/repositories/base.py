from typing import TypeVar, Generic, Type, Optional, List, Any, Protocol
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from utils.logging import get_logger

logger = get_logger(__name__)


# Protocol for SQLAlchemy models with id attribute
class HasId(Protocol):
    id: Any


# Generic type for SQLAlchemy models
ModelType = TypeVar("ModelType", bound=HasId)


class BaseRepository(Generic[ModelType]):
    """Base repository class with common CRUD operations"""

    def __init__(self, model: Type[ModelType]):
        """
        Initialize repository with model class

        Args:
            model: SQLAlchemy model class
        """
        self.model = model

    async def get_by_id(self, session: AsyncSession, id: int) -> Optional[ModelType]:
        """
        Get record by primary key ID

        Args:
            session: Database session
            id: Primary key ID

        Returns:
            Model instance or None if not found
        """
        try:
            result = await session.execute(select(self.model).where(self.model.id == id))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("get_by_id_error", model=self.model.__name__, id=id, error=str(e))
            raise

    async def get_by_field(
        self, session: AsyncSession, field_name: str, field_value: Any
    ) -> Optional[ModelType]:
        """
        Get record by specific field

        Args:
            session: Database session
            field_name: Field name to search by
            field_value: Field value to match

        Returns:
            Model instance or None if not found
        """
        try:
            field = getattr(self.model, field_name)
            result = await session.execute(select(self.model).where(field == field_value))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                "get_by_field_error",
                model=self.model.__name__,
                field=field_name,
                value=field_value,
                error=str(e),
            )
            raise

    async def get_all(
        self, session: AsyncSession, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> List[ModelType]:
        """
        Get all records with optional pagination

        Args:
            session: Database session
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of model instances
        """
        try:
            query = select(self.model)
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error("get_all_error", model=self.model.__name__, error=str(e))
            raise

    async def create(self, session: AsyncSession, **kwargs) -> ModelType:
        """
        Create new record

        Args:
            session: Database session
            **kwargs: Field values for the new record

        Returns:
            Created model instance
        """
        try:
            instance = self.model(**kwargs)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)

            logger.info("record_created", model=self.model.__name__, id=getattr(instance, "id", None))
            return instance
        except IntegrityError as e:
            await session.rollback()
            logger.error("create_integrity_error", model=self.model.__name__, error=str(e))
            raise
        except Exception as e:
            await session.rollback()
            logger.error("create_error", model=self.model.__name__, error=str(e))
            raise

    async def update(self, session: AsyncSession, instance: ModelType, **kwargs) -> ModelType:
        """
        Update existing record

        Args:
            session: Database session
            instance: Model instance to update
            **kwargs: Field values to update

        Returns:
            Updated model instance
        """
        try:
            for field, value in kwargs.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)

            await session.commit()
            await session.refresh(instance)

            logger.info("record_updated", model=self.model.__name__, id=getattr(instance, "id", None))
            return instance
        except Exception as e:
            await session.rollback()
            logger.error("update_error", model=self.model.__name__, error=str(e))
            raise

    async def delete(self, session: AsyncSession, instance: ModelType) -> bool:
        """
        Delete record

        Args:
            session: Database session
            instance: Model instance to delete

        Returns:
            True if deleted successfully
        """
        try:
            await session.delete(instance)
            await session.commit()

            logger.info("record_deleted", model=self.model.__name__, id=getattr(instance, "id", None))
            return True
        except Exception as e:
            await session.rollback()
            logger.error("delete_error", model=self.model.__name__, error=str(e))
            return False

    async def count(self, session: AsyncSession, **filters) -> int:
        """
        Count records with optional filters

        Args:
            session: Database session
            **filters: Field filters

        Returns:
            Number of matching records
        """
        try:
            query = select(func.count(self.model.id))

            # Apply filters
            for field_name, field_value in filters.items():
                if hasattr(self.model, field_name):
                    field = getattr(self.model, field_name)
                    query = query.where(field == field_value)

            result = await session.execute(query)
            return result.scalar() or 0
        except Exception as e:
            logger.error("count_error", model=self.model.__name__, error=str(e))
            raise

    async def exists(self, session: AsyncSession, **filters) -> bool:
        """
        Check if record exists with given filters

        Args:
            session: Database session
            **filters: Field filters

        Returns:
            True if record exists
        """
        try:
            count = await self.count(session, **filters)
            return count > 0
        except Exception as e:
            logger.error("exists_error", model=self.model.__name__, error=str(e))
            raise

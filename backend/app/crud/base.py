from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.ext.declarative import DeclarativeMeta

from utils.logging import get_logger, bind_context

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
        """Create a new record with strict validation."""
        # Create contextualized logger for this operation
        op_logger = bind_context(logger, operation="create", model=self.model.__name__)

        # Strict validation - check if obj_in is valid
        if not obj_in:
            op_logger.error("empty_create_data", model=self.model.__name__)
            raise ValueError("obj_in cannot be empty")

        # Validate data types and log problematic values
        validation_warnings = []
        for key, value in obj_in.items():
            if value is None:
                validation_warnings.append(f"Field '{key}' is None")
            elif isinstance(value, str) and not value.strip():
                validation_warnings.append(f"Field '{key}' is empty string")

        if validation_warnings:
            op_logger.warning(
                "create_validation_warnings",
                warnings=validation_warnings,
                data=obj_in,
                action="proceeding_with_create_for_data_integrity",
            )

        try:
            # Check which fields are valid for the model
            valid_fields = {}
            invalid_fields = []

            for key, value in obj_in.items():
                if hasattr(self.model, key):
                    valid_fields[key] = value
                else:
                    invalid_fields.append(key)
                    op_logger.error(
                        "invalid_field_in_create",
                        field=key,
                        value=value,
                        model=self.model.__name__,
                        action="field_ignored",
                    )

            if invalid_fields:
                op_logger.warning(
                    "some_fields_ignored_in_create",
                    invalid_fields=invalid_fields,
                    valid_fields=list(valid_fields.keys()),
                    model=self.model.__name__,
                )

            db_obj = self.model(**valid_fields)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)

            op_logger.info(
                "record_created_successfully",
                model=self.model.__name__,
                record_id=getattr(db_obj, "id", None),
                valid_fields=list(valid_fields.keys()),
                ignored_fields=invalid_fields,
                validation_warnings=validation_warnings,
            )

            return db_obj

        except Exception as e:
            await db.rollback()
            op_logger.error(
                "record_creation_failed",
                model=self.model.__name__,
                error=str(e),
                data=obj_in,
                validation_warnings=validation_warnings,
            )
            raise

    async def update(self, db: AsyncSession, *, db_obj: ModelType, obj_in: Dict[str, Any]) -> ModelType:
        """Update an existing record with strict validation."""
        # Create contextualized logger for this operation
        op_logger = bind_context(logger, operation="update", model=self.model.__name__)

        # Strict validation - check if obj_in is valid
        if not obj_in:
            op_logger.error("empty_update_data", model=self.model.__name__)
            raise ValueError("obj_in cannot be empty")

        if not db_obj:
            op_logger.error("null_db_object", model=self.model.__name__)
            raise ValueError("db_obj cannot be None")

        # Log all fields being updated for audit trail
        record_id = getattr(db_obj, "id", None)
        op_logger.info(
            "updating_record_fields",
            model=self.model.__name__,
            record_id=record_id,
            fields=list(obj_in.keys()),
            values_count=len(obj_in),
        )

        # Check for potentially problematic values and log them
        validation_warnings = []
        for key, value in obj_in.items():
            if value is None:
                validation_warnings.append(f"Field '{key}' is being set to None")
            elif isinstance(value, str) and not value.strip():
                validation_warnings.append(f"Field '{key}' is being set to empty string")

        if validation_warnings:
            op_logger.warning(
                "update_validation_warnings",
                warnings=validation_warnings,
                data=obj_in,
                record_id=record_id,
                action="proceeding_with_update_for_data_integrity",
            )

        try:
            # Track which fields actually exist on the model
            valid_fields = []
            invalid_fields = []

            for field, value in obj_in.items():
                if hasattr(db_obj, field):
                    old_value = getattr(db_obj, field)
                    setattr(db_obj, field, value)
                    valid_fields.append(field)

                    # Log significant changes
                    if old_value != value:
                        op_logger.info(
                            "field_updated",
                            model=self.model.__name__,
                            record_id=record_id,
                            field=field,
                            old_value=old_value,
                            new_value=value,
                        )
                else:
                    invalid_fields.append(field)
                    op_logger.error(
                        "invalid_field_in_update",
                        field=field,
                        value=value,
                        model=self.model.__name__,
                        record_id=record_id,
                        action="field_ignored",
                    )

            if invalid_fields:
                op_logger.warning(
                    "some_fields_ignored_in_update",
                    invalid_fields=invalid_fields,
                    valid_fields=valid_fields,
                    model=self.model.__name__,
                    record_id=record_id,
                )

            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)

            op_logger.info(
                "record_updated_successfully",
                model=self.model.__name__,
                record_id=record_id,
                updated_fields=valid_fields,
                ignored_fields=invalid_fields,
                validation_warnings=validation_warnings,
            )

            return db_obj

        except Exception as e:
            await db.rollback()
            op_logger.error(
                "record_update_failed",
                model=self.model.__name__,
                record_id=record_id,
                error=str(e),
                data=obj_in,
                validation_warnings=validation_warnings,
            )
            raise

    async def remove(self, db: AsyncSession, *, id: int) -> Optional[ModelType]:
        """Remove a record by ID."""
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

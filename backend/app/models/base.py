"""
Base model classes for SQLAlchemy models.

This module provides base classes with common fields and functionality
that are shared across all database models.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from utils.snowflake import generate_snowflake_id


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class TimestampMixin:
    """Mixin for models that need created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), comment="Record creation timestamp"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        comment="Record last update timestamp",
    )


class SnowflakeIDMixin:
    """Mixin for models that use Snowflake IDs as primary keys."""

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, default=generate_snowflake_id, comment="Snowflake ID primary key"
    )


class AutoIncrementIDMixin:
    """Mixin for models that use auto-increment IDs as primary keys."""

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="Auto-increment ID primary key"
    )


class QiaoIDMixin:
    """Mixin for models that have external qiao_id identifiers."""

    qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, comment="External identifier: qiao_+random"
    )


class BaseModel(Base, TimestampMixin):
    """
    Abstract base model with common functionality.

    This class should not be instantiated directly.
    Use SnowflakeModel or AutoIncrementModel instead.
    """

    __abstract__ = True

    def to_dict(self, exclude: Optional[set] = None) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.

        Args:
            exclude: Set of field names to exclude from the result

        Returns:
            Dict containing model data
        """
        exclude = exclude or set()
        result = {}

        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                # Convert datetime objects to ISO format strings
                if isinstance(value, datetime):
                    value = value.isoformat()
                result[column.name] = value

        return result

    def update_from_dict(self, data: Dict[str, Any], exclude: Optional[set] = None) -> None:
        """
        Update model instance from dictionary.

        Args:
            data: Dictionary containing field values
            exclude: Set of field names to exclude from update
        """
        exclude = exclude or {"id", "created_at"}

        for key, value in data.items():
            if key not in exclude and hasattr(self, key):
                setattr(self, key, value)


class SnowflakeModel(BaseModel, SnowflakeIDMixin):
    """
    Base model for entities that use Snowflake IDs.

    Use this for core business entities like users, messages, AI characters, etc.
    """

    __abstract__ = True


class AutoIncrementModel(BaseModel, AutoIncrementIDMixin):
    """
    Base model for entities that use auto-increment IDs.

    Use this for configuration tables, statistics, and other auxiliary data.
    """

    __abstract__ = True


class SnowflakeQiaoModel(SnowflakeModel, QiaoIDMixin):
    """
    Base model for entities that use both Snowflake IDs and qiao_id.

    Use this for entities that need external identifiers for API exposure.
    """

    __abstract__ = True


class StatusMixin:
    """Mixin for models that have a status field."""

    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="Entity status")


class SoftDeleteMixin:
    """Mixin for models that support soft deletion."""

    is_deleted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Soft delete flag: 1=deleted, 0=active"
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="Deletion timestamp"
    )

    def soft_delete(self) -> None:
        """Mark the record as deleted."""
        self.is_deleted = 1
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.is_deleted = 0
        self.deleted_at = None


class UserOwnedMixin:
    """Mixin for models that belong to a specific user."""

    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Owner user internal ID"
    )

    user_qiao_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="Owner user external ID"
    )

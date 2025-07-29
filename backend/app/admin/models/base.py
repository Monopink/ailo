from datetime import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy import Column, Integer, DateTime, func

# Use the same base as the main project
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.base import Base


class AdminBaseModel(Base):
    """Base model for admin module, inheriting from main project's Base"""

    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    def to_dict(self, exclude_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert model instance to dictionary"""
        if exclude_fields is None:
            exclude_fields = []

        result = {}
        for column in self.__table__.columns:
            if column.name not in exclude_fields:
                value = getattr(self, column.name)
                if isinstance(value, datetime):
                    # Format datetime to string
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                result[column.name] = value

        return result

    @classmethod
    def get_table_name(cls) -> str:
        """Get table name"""
        return cls.__tablename__


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""

    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), index=True)

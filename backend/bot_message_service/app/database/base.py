"""
Database base class and common utilities.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy import Column, Integer, DateTime


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class TimestampMixin:
    """Mixin to add timestamp fields to models."""
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=datetime.now(timezone.utc))
    
    @declared_attr  
    def updated_at(cls):
        return Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

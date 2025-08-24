"""
Common schemas for API requests and responses.

This module contains base schemas and common response formats
used across the application.
"""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field


# Generic type for data responses
DataT = TypeVar("DataT")


class BaseResponse(BaseModel, Generic[DataT]):
    """Base response schema for all API responses."""

    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[DataT] = Field(None, description="Response data")
    message: Optional[str] = Field(None, description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class ErrorResponse(BaseModel):
    """Error response schema."""

    success: bool = Field(False, description="Always false for error responses")
    error: Dict[str, Any] = Field(..., description="Error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    path: Optional[str] = Field(None, description="Request path where error occurred")


class PaginationParams(BaseModel):
    """Pagination parameters for list requests."""

    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of records to return")


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Paginated response schema."""

    success: bool = Field(True, description="Whether the request was successful")
    data: List[DataT] = Field(..., description="List of items")
    total: int = Field(..., ge=0, description="Total number of items")
    skip: int = Field(..., ge=0, description="Number of items skipped")
    limit: int = Field(..., ge=1, description="Maximum number of items returned")
    has_more: bool = Field(..., description="Whether there are more items available")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class SuccessResponse(BaseModel):
    """Simple success response without data."""

    success: bool = Field(True, description="Whether the request was successful")
    message: str = Field(..., description="Success message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class IDResponse(BaseModel):
    """Response containing only an ID."""

    success: bool = Field(True, description="Whether the request was successful")
    data: Dict[str, str] = Field(..., description="ID data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

    @classmethod
    def create(cls, id_field: str, id_value: str) -> "IDResponse":
        """Create an ID response."""
        return cls(data={id_field: id_value})


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    class Config:
        # Allow population from SQLAlchemy models
        from_attributes = True
        # Use enum values instead of enum names
        use_enum_values = True
        # Validate assignment
        validate_assignment = True
        # Allow extra fields to be ignored
        extra = "ignore"

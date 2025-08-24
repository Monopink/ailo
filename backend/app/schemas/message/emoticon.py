"""
Emoticon related schemas.

This module contains Pydantic schemas for emoticon management.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from enums import EmoticonCategory, EmoticonCreatorType
from schemas.common import BaseSchema


# Emoticon Schemas


class EmoticonBase(BaseSchema):
    """Base emoticon schema."""

    code: str = Field(..., max_length=50, description="Unique identifier")
    category: EmoticonCategory = Field(..., description="Emoticon category")
    description: Optional[str] = Field(None, max_length=200, description="Emoticon description")


class EmoticonCreate(BaseModel):
    """Schema for creating a new emoticon."""

    code: str = Field(..., max_length=50, description="Unique identifier")
    category: EmoticonCategory = Field(..., description="Emoticon category")
    file_id: Optional[str] = Field(None, max_length=32, description="Media file ID")
    url: Optional[str] = Field(None, max_length=500, description="Image URL")
    description: Optional[str] = Field(None, max_length=200, description="Emoticon description")
    sort_order: int = Field(0, description="Sort order")


class EmoticonUpdate(BaseModel):
    """Schema for updating emoticon information."""

    description: Optional[str] = Field(None, max_length=200, description="Emoticon description")
    url: Optional[str] = Field(None, max_length=500, description="Image URL")
    sort_order: Optional[int] = Field(None, description="Sort order")
    status: Optional[int] = Field(None, description="Status")


class EmoticonResponse(EmoticonBase):
    """Schema for emoticon response data."""

    file_id: Optional[str] = Field(None, description="Media file ID")
    url: Optional[str] = Field(None, description="Image URL")
    created_by_type: EmoticonCreatorType = Field(..., description="Creator type")
    created_by_id: int = Field(..., description="Creator internal ID")
    status: int = Field(..., description="Status")
    sort_order: int = Field(..., description="Sort order")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class EmoticonListResponse(BaseSchema):
    """Schema for emoticon list item (minimal info)."""

    code: str = Field(..., description="Unique identifier")
    category: EmoticonCategory = Field(..., description="Emoticon category")
    url: Optional[str] = Field(None, description="Image URL")
    description: Optional[str] = Field(None, description="Emoticon description")
    sort_order: int = Field(..., description="Sort order")


# Emoticon Query Schemas


class EmoticonQuery(BaseModel):
    """Schema for querying emoticons."""

    category: Optional[EmoticonCategory] = Field(None, description="Filter by category")
    creator_type: Optional[EmoticonCreatorType] = Field(None, description="Filter by creator type")
    status: Optional[int] = Field(None, description="Filter by status")
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of records")


class EmoticonSearch(BaseModel):
    """Schema for searching emoticons."""

    query: str = Field(..., min_length=1, max_length=50, description="Search query")
    category: Optional[EmoticonCategory] = Field(None, description="Filter by category")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")


# Emoticon Statistics


class EmoticonStats(BaseSchema):
    """Schema for emoticon statistics."""

    total_emoticons: int = Field(..., description="Total emoticon count")
    emoticons_by_category: dict = Field(..., description="Emoticon count by category")
    emoticons_by_creator: dict = Field(..., description="Emoticon count by creator type")
    active_emoticons: int = Field(..., description="Active emoticon count")
    inactive_emoticons: int = Field(..., description="Inactive emoticon count")

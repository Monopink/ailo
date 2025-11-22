"""
Discovery page schemas.

This module contains Pydantic schemas for discovery page operations.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enums import ExposureStrategy, SquareCategory


class SquareContactResponse(BaseModel):
    """Square page contact response."""

    qiao_id: str = Field(..., description="Contact qiao_id")
    category: Optional[int] = Field(None, description="Category (1-5)")
    type_id: int = Field(..., description="AI type identifier backing this entry")
    nickname: Optional[str] = Field(None, description="Persona nickname")
    gender: Optional[int] = Field(None, description="Gender: 1=male, 2=female, 3=other, 4=unknown")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    bio: Optional[str] = Field(None, description="Bio/description")
    region: Optional[str] = Field(None, description="Region/location")

    class Config:
        from_attributes = True


class PaginationInfo(BaseModel):
    """Pagination information."""

    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total items count")
    has_more: bool = Field(..., description="Whether there are more items")


class SquareContactListResponse(BaseModel):
    """Square contact list response."""

    items: List[SquareContactResponse] = Field(..., description="Contact list")
    pagination: PaginationInfo = Field(..., description="Pagination information")


class SquareEntryBase(BaseModel):
    """Base schema for Square exposure entries."""

    square_category: SquareCategory = Field(..., description="Square category (1=friend, 2=love, 3=talk, 4=bestie, 5=hobby)")
    type_id: int = Field(..., description="AI type exposed in this slot")
    exposure_strategy: ExposureStrategy = Field(ExposureStrategy.RANDOM, description="Exposure strategy (1=random)")
    status: int = Field(1, ge=1, le=2, description="Status: 1=active, 2=inactive")


class SquareEntryCreate(SquareEntryBase):
    """Schema for creating Square exposure entries."""

    pass


class SquareEntryUpdate(BaseModel):
    """Schema for updating Square exposure entries."""

    square_category: Optional[SquareCategory] = Field(None, description="Square category (1-5)")
    type_id: Optional[int] = Field(None, description="AI type exposed in this slot")
    exposure_strategy: Optional[ExposureStrategy] = Field(None, description="Exposure strategy (1=random)")
    status: Optional[int] = Field(None, ge=1, le=2, description="Status: 1=active, 2=inactive")

class SquareEntry(SquareEntryBase):
    """Square exposure entry response."""

    id: int = Field(..., description="Entry ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class SquareEntryListResponse(BaseModel):
    """Paginated response for square entries."""

    items: List[SquareEntry] = Field(..., description="Square entries")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")


class StrangerProfileResponse(BaseModel):
    """Stranger profile response (public profile without contact relationship)."""

    qiao_id: str = Field(..., description="Profile qiao_id")
    nickname: Optional[str] = Field(None, description="Nickname")
    gender: Optional[int] = Field(None, description="Gender: 1=male, 2=female, 3=other, 4=unknown")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    bio: Optional[str] = Field(None, description="Bio/description")
    region: Optional[str] = Field(None, description="Region/location")
    category: Optional[int] = Field(None, description="Category (1-5)")

    class Config:
        from_attributes = True

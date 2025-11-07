"""
Discovery page schemas.

This module contains Pydantic schemas for discovery page operations.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class SquareContactResponse(BaseModel):
    """Square page contact response."""

    qiao_id: str = Field(..., description="Contact qiao_id")
    category: Optional[int] = Field(None, description="Category (1-5)")
    nickname: Optional[str] = Field(None, description="Nickname")
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

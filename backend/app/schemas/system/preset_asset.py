"""
Preset asset related schemas.

This module contains Pydantic schemas for preset asset management.
"""

from typing import Optional
from pydantic import BaseModel, Field

from schemas.common import BaseSchema


class PresetAssetBase(BaseSchema):
    """Base preset asset schema."""

    asset_type: int = Field(..., ge=1, le=2, description="Asset type: 1=avatar, 2=emoticon")
    name: str = Field(..., max_length=50, description="Unique asset name")
    category: int = Field(..., description="Asset category")
    is_client_preset: int = Field(1, ge=0, le=1, description="Is bundled with client: 1=yes, 0=no")
    file_id: Optional[int] = Field(None, description="Media file ID (optional)")
    url: str = Field(..., max_length=500, description="Asset URL")
    prompt: Optional[str] = Field(None, description="AI generation prompt (optional)")
    description: Optional[str] = Field(None, max_length=200, description="Asset description")
    status: int = Field(1, ge=1, le=2, description="Status: 1=active, 2=inactive")
    sort_order: int = Field(0, description="Display order")


class PresetAssetCreate(BaseModel):
    """Schema for creating preset asset."""

    asset_type: int = Field(..., ge=1, le=2, description="Asset type: 1=avatar, 2=emoticon")
    name: str = Field(..., max_length=50, description="Unique asset name")
    category: int = Field(..., description="Asset category")
    is_client_preset: int = Field(1, ge=0, le=1, description="Is bundled with client")
    file_id: Optional[int] = Field(None, description="Media file ID")
    url: str = Field(..., max_length=500, description="Asset URL")
    prompt: Optional[str] = Field(None, description="AI generation prompt")
    description: Optional[str] = Field(None, max_length=200, description="Description")
    status: int = Field(1, ge=1, le=2, description="Status")
    sort_order: int = Field(0, description="Sort order")


class PresetAssetUpdate(BaseModel):
    """Schema for updating preset asset."""

    asset_type: Optional[int] = Field(None, ge=1, le=2, description="Asset type")
    name: Optional[str] = Field(None, max_length=50, description="Asset name")
    category: Optional[int] = Field(None, description="Asset category")
    is_client_preset: Optional[int] = Field(None, ge=0, le=1, description="Is client preset")
    file_id: Optional[int] = Field(None, description="Media file ID")
    url: Optional[str] = Field(None, max_length=500, description="Asset URL")
    prompt: Optional[str] = Field(None, description="AI generation prompt")
    description: Optional[str] = Field(None, max_length=200, description="Description")
    status: Optional[int] = Field(None, ge=1, le=2, description="Status")
    sort_order: Optional[int] = Field(None, description="Sort order")


class PresetAssetResponse(PresetAssetBase):
    """Schema for preset asset response."""

    id: int = Field(..., description="Asset ID")

    class Config:
        from_attributes = True


class PresetAssetListResponse(BaseModel):
    """Schema for preset asset list response."""

    total: int = Field(..., description="Total count")
    items: list[PresetAssetResponse] = Field(..., description="Asset list")

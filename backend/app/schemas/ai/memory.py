"""AI memory schemas.

Defines Pydantic models for template memories and instance memories so that
CRUD layers and APIs can share the same validation logic.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MemoryType = Literal["core", "recent"]


class AITemplateMemoryBase(BaseModel):
    """Base schema for template memories."""

    template_id: int = Field(..., description="Associated ai_templates.id")
    memory_type: MemoryType = Field(..., description="Memory type: core/recent")
    content: str = Field(..., min_length=1, description="Memory content")
    importance: int = Field(..., ge=1, le=10, description="Importance score (1-10)")
    display_order: int = Field(0, ge=0, description="Copy/display order (lower first)")


class AITemplateMemoryCreate(AITemplateMemoryBase):
    """Schema for creating template memories."""


class AITemplateMemoryUpdate(BaseModel):
    """Schema for updating template memories."""

    memory_type: MemoryType | None = Field(None, description="Memory type")
    content: str | None = Field(None, min_length=1, description="Memory content")
    importance: int | None = Field(None, ge=1, le=10, description="Importance score (1-10)")
    display_order: int | None = Field(None, ge=0, description="Copy/display order")


class AITemplateMemory(AITemplateMemoryBase):
    """Template memory response schema."""

    id: int = Field(..., description="Memory ID")
    created_at: str | None = Field(None, description="Creation timestamp")
    updated_at: str | None = Field(None, description="Last update timestamp")

    class Config:
        """Allow ORM models to populate this schema."""

        from_attributes = True


class AIInstanceMemoryBase(BaseModel):
    """Base schema for instance memories."""

    instance_id: int = Field(..., description="AI instance ID")
    instance_qiao_id: str = Field(..., min_length=1, description="Instance qiao_id")
    user_id: int = Field(..., description="Owning user ID")
    user_qiao_id: str = Field(..., min_length=1, description="User qiao_id")
    memory_type: MemoryType = Field(..., description="Memory type: core/recent")
    content: str = Field(..., min_length=1, description="Memory content")
    importance: int = Field(..., ge=1, le=10, description="Importance score (1-10)")
    status: int = Field(1, ge=1, le=2, description="Status: 1=active, 2=archived")
    source_message_id: int | None = Field(None, description="Source conversation item ID")


class AIInstanceMemoryCreate(AIInstanceMemoryBase):
    """Schema for creating instance memories."""


class AIInstanceMemoryUpdate(BaseModel):
    """Schema for updating instance memories."""

    content: str | None = Field(None, min_length=1, description="Memory content")
    memory_type: MemoryType | None = Field(None, description="Memory type")
    importance: int | None = Field(None, ge=1, le=10, description="Importance score")
    status: int | None = Field(None, ge=1, le=2, description="Status flag")
    refreshed_at: str | None = Field(None, description="Refresh timestamp")
    expires_at: str | None = Field(None, description="Expiration timestamp")
    source_message_id: int | None = Field(None, description="Source conversation item ID")


class AIInstanceMemory(AIInstanceMemoryBase):
    """Instance memory response schema."""

    id: int = Field(..., description="Memory ID")
    refreshed_at: str | None = Field(None, description="Last refresh timestamp")
    expires_at: str | None = Field(None, description="Expiration timestamp")
    created_at: str | None = Field(None, description="Creation timestamp")
    updated_at: str | None = Field(None, description="Last update timestamp")

    class Config:
        """Allow ORM models to populate this schema."""

        from_attributes = True


__all__ = [
    "AIInstanceMemory",
    "AIInstanceMemoryBase",
    "AIInstanceMemoryCreate",
    "AIInstanceMemoryUpdate",
    "AITemplateMemory",
    "AITemplateMemoryBase",
    "AITemplateMemoryCreate",
    "AITemplateMemoryUpdate",
    "MemoryType",
]

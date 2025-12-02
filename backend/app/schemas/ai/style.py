"""
AI style related schemas.

This module contains Pydantic schemas for AI styles and relationships.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from schemas.common import BaseSchema

# AI Style Schemas


class AIStyleBase(BaseSchema):
    """Base AI style schema."""

    display_name: str = Field(..., max_length=100, description="Display name")


class AIStyleCreate(BaseModel):
    """Schema for creating an AI style."""

    display_name: str = Field(..., max_length=100, description="Display name")


class AIStyleUpdate(BaseModel):
    """Schema for updating an AI style."""

    display_name: str | None = Field(None, max_length=100, description="Display name")
    status: int | None = Field(None, ge=1, le=2, description="Status: 1=active, 2=inactive")


class AIStyleResponse(AIStyleBase):
    """Schema for AI style response data."""

    initial_relationship_id: int | None = Field(None, description="Initial relationship type ID")
    status: int = Field(..., description="Status")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# Dimension Schemas


class AIDimensionBase(BaseSchema):
    """Base AI dimension schema (global)."""

    name: str = Field(..., max_length=50, description="Dimension name (unique)")
    display_name: str | None = Field(None, max_length=100, description="Display name for UI")
    description: str | None = Field(None, description="Dimension description")


class AIDimensionCreate(BaseModel):
    """Schema for creating a global AI dimension."""

    name: str = Field(..., max_length=50, description="Dimension name (unique)")
    display_name: str | None = Field(None, max_length=100, description="Display name for UI")
    description: str | None = Field(None, description="Dimension description")


class AIDimensionUpdate(BaseModel):
    """Schema for updating a global AI dimension."""

    name: str | None = Field(None, max_length=50, description="Dimension name (unique)")
    display_name: str | None = Field(None, max_length=100, description="Display name for UI")
    description: str | None = Field(None, description="Dimension description")


class AIDimensionResponse(AIDimensionBase):
    """Schema for AI dimension response data."""

    id: int = Field(..., description="Dimension ID")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# AI Style Dimension Schemas (junction)


class AIStyleDimensionBase(BaseSchema):
    """Base AI style dimension schema (junction style<->dimension)."""

    style_id: int = Field(..., description="Style ID")
    dimension_id: int = Field(..., description="Dimension ID")
    initial_position: int = Field(
        ..., ge=0, le=1000, description="Initial position, 0-1000 per mille"
    )


class AIStyleDimensionCreate(BaseModel):
    """Schema for creating an AI style dimension mapping."""

    style_id: int = Field(..., description="Style ID")
    dimension_id: int = Field(..., description="Dimension ID")
    initial_position: int = Field(
        ..., ge=0, le=1000, description="Initial position, 0-1000 per mille"
    )


class AIStyleDimensionUpdate(BaseModel):
    """Schema for updating an AI style dimension mapping."""

    dimension_id: int | None = Field(None, description="Dimension ID")
    initial_position: int | None = Field(
        None, ge=0, le=1000, description="Initial position, 0-1000 per mille"
    )


class AIStyleDimensionResponse(AIStyleDimensionBase):
    """Schema for AI style dimension response data."""

    id: int = Field(..., description="Dimension ID")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# AI Relationship Schemas


class AIRelationshipBase(BaseSchema):
    """Base AI relationship schema."""

    display_name: str = Field(..., max_length=100, description="Display name")
    prompt_fragment: str | None = Field(None, description="Prompt fragment for this relationship")


class AIRelationshipCreate(BaseModel):
    """Schema for creating an AI relationship."""

    display_name: str = Field(..., max_length=100, description="Display name")
    prompt_fragment: str | None = Field(None, description="Prompt fragment for this relationship")


class AIRelationshipResponse(AIRelationshipBase):
    """Schema for AI relationship response data."""

    status: int = Field(..., description="Status")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# AI Dimension Relationship Mapping Schemas (global)


class AIDimensionRelationshipMappingBase(BaseSchema):
    """Base AI dimension relationship mapping schema (global)."""

    dimension_id: int = Field(..., description="Dimension ID")
    start_position: int = Field(..., ge=0, le=1000, description="Start position, 0-1000 per mille")
    end_position: int = Field(..., ge=0, le=1000, description="End position, 0-1000 per mille")
    relationship_id: int = Field(..., description="Relationship ID")
    priority: int = Field(..., description="Priority")
    limit_count: int | None = Field(None, description="Maximum occurrence count")


class AIDimensionRelationshipMappingCreate(BaseModel):
    """Schema for creating an AI dimension relationship mapping."""

    dimension_id: int = Field(..., description="Dimension ID")
    start_position: int = Field(..., ge=0, le=1000, description="Start position, 0-1000 per mille")
    end_position: int = Field(..., ge=0, le=1000, description="End position, 0-1000 per mille")
    relationship_id: int = Field(..., description="Relationship ID")
    priority: int = Field(..., description="Priority")
    limit_count: int | None = Field(None, description="Maximum occurrence count")

    @field_validator("end_position")
    @classmethod
    def validate_position_range(cls, v, info):
        """Validate end_position is greater than start_position."""
        if info.data and "start_position" in info.data:
            start_position = info.data["start_position"]
            if v <= start_position:
                raise ValueError("end_position must be greater than start_position")
        return v


class AIDimensionRelationshipMappingUpdate(BaseModel):
    """Schema for updating an AI dimension relationship mapping."""

    dimension_id: int | None = Field(None, description="Dimension ID")
    start_position: int | None = Field(
        None, ge=0, le=1000, description="Start position, 0-1000 per mille"
    )
    end_position: int | None = Field(
        None, ge=0, le=1000, description="End position, 0-1000 per mille"
    )
    relationship_id: int | None = Field(None, description="Relationship ID")
    priority: int | None = Field(None, description="Priority level")
    limit_count: int | None = Field(
        None, description="Maximum occurrence count, NULL means unlimited"
    )

    @field_validator("end_position")
    @classmethod
    def validate_score_range(cls, v, info):
        """Validate end_position is greater than start_position."""
        if v is not None and info.data and "start_position" in info.data:
            start_position = info.data["start_position"]
            if start_position is not None and v <= start_position:
                raise ValueError("end_position must be greater than start_position")
        return v


class AIDimensionRelationshipMappingResponse(AIDimensionRelationshipMappingBase):
    """Schema for AI dimension relationship mapping response data."""

    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")

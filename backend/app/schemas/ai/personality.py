"""
AI personality related schemas.

This module contains Pydantic schemas for AI personalities and templates.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from schemas.common import BaseSchema

# AI Personality Schemas


class AIPersonalityBase(BaseSchema):
    """Base AI personality schema."""

    display_name: str = Field(..., max_length=100, description="Display name")
    prompt: str = Field(..., description="Personality prompt template")
    json_schema: dict[str, Any] | None = Field(None, description="JSON schema definition")


class AIPersonalityCreate(BaseModel):
    """Schema for creating an AI personality."""

    display_name: str = Field(..., max_length=100, description="Display name")
    prompt: str = Field(..., min_length=1, description="Personality prompt template")
    json_schema: dict[str, Any] | None = Field(None, description="JSON schema definition")


class AIPersonalityUpdate(BaseModel):
    """Schema for updating an AI personality."""

    display_name: str | None = Field(None, max_length=100, description="Display name")
    prompt: str | None = Field(None, min_length=1, description="Personality prompt template")
    json_schema: dict[str, Any] | None = Field(None, description="JSON schema definition")
    status: int | None = Field(
        None, ge=1, le=3, description="Status: 1=active, 2=inactive (follow enum design)"
    )


class AIPersonalityResponse(AIPersonalityBase):
    """Schema for AI personality response data."""

    status: int = Field(..., description="Status")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# AI Personality Placeholder Schemas


class AIPersonalityPlaceholderBase(BaseSchema):
    """Base AI personality placeholder schema."""

    personality_id: int = Field(..., description="Personality ID")
    placeholder_key: str = Field(..., max_length=100, description="Placeholder key name")
    display_name: str | None = Field(None, max_length=200, description="Display name for UI")
    description: str | None = Field(None, max_length=500, description="Placeholder description")
    example_value: str | None = Field(None, description="Example placeholder value")
    is_required: bool = Field(False, description="Is required")


class AIPersonalityPlaceholderCreate(BaseModel):
    """Schema for creating an AI personality placeholder."""

    personality_id: int = Field(..., description="Personality ID")
    placeholder_key: str = Field(..., max_length=100, description="Placeholder key name")
    display_name: str | None = Field(None, max_length=200, description="Display name for UI")
    description: str | None = Field(None, max_length=500, description="Placeholder description")
    example_value: str | None = Field(None, description="Example placeholder value")
    is_required: bool = Field(False, description="Is required")


class AIPersonalityPlaceholderUpdate(BaseModel):
    """Schema for updating an AI personality placeholder."""

    display_name: str | None = Field(None, max_length=200, description="Display name for UI")
    description: str | None = Field(None, max_length=500, description="Placeholder description")
    example_value: str | None = Field(None, description="Example placeholder value")
    is_required: bool | None = Field(None, description="Is required")


class AIPersonalityPlaceholderResponse(AIPersonalityPlaceholderBase):
    """Schema for AI personality placeholder response data."""

    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")

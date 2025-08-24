"""
AI personality related schemas.

This module contains Pydantic schemas for AI personalities and templates.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from schemas.common import BaseSchema


# AI Personality Schemas


class AIPersonalityBase(BaseSchema):
    """Base AI personality schema."""

    name: str = Field(..., max_length=100, description="Personality name")
    prompt: str = Field(..., description="Personality prompt template")
    json_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema definition")


class AIPersonalityCreate(BaseModel):
    """Schema for creating an AI personality."""

    name: str = Field(..., max_length=100, description="Personality name")
    prompt: str = Field(..., min_length=1, description="Personality prompt template")
    json_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema definition")


class AIPersonalityResponse(AIPersonalityBase):
    """Schema for AI personality response data."""

    usage_count: int = Field(..., description="Reference count")
    status: int = Field(..., description="Status")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# AI Personality Placeholder Schemas


class AIPersonalityPlaceholderBase(BaseSchema):
    """Base AI personality placeholder schema."""

    personality_id: int = Field(..., description="Personality ID")
    placeholder_key: str = Field(..., max_length=100, description="Placeholder key name")
    placeholder_type: int = Field(..., description="Placeholder type: 1=text, 2=number, 3=boolean, 4=list")
    default_value: Optional[str] = Field(None, description="Default placeholder value")
    description: Optional[str] = Field(None, max_length=500, description="Placeholder description")
    is_required: bool = Field(False, description="Is required")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="Validation rules")


class AIPersonalityPlaceholderCreate(BaseModel):
    """Schema for creating an AI personality placeholder."""

    personality_id: int = Field(..., description="Personality ID")
    placeholder_key: str = Field(..., max_length=100, description="Placeholder key name")
    placeholder_type: int = Field(
        ..., ge=1, le=4, description="Placeholder type: 1=text, 2=number, 3=boolean, 4=list"
    )
    default_value: Optional[str] = Field(None, description="Default placeholder value")
    description: Optional[str] = Field(None, max_length=500, description="Placeholder description")
    is_required: bool = Field(False, description="Is required")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="Validation rules")


class AIPersonalityPlaceholderResponse(AIPersonalityPlaceholderBase):
    """Schema for AI personality placeholder response data."""

    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# AI Template Schemas


class AIInfoTemplateBase(BaseSchema):
    """Base AI info template schema."""

    name: str = Field(..., max_length=100, description="Template name")
    prompt: str = Field(..., description="Core prompt template")
    json_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema definition")


class AIInfoTemplateCreate(BaseModel):
    """Schema for creating an AI info template."""

    name: str = Field(..., max_length=100, description="Template name")
    prompt: str = Field(..., min_length=1, description="Core prompt template")
    json_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema definition")


class AIInfoTemplateResponse(AIInfoTemplateBase):
    """Schema for AI info template response data."""

    usage_count: int = Field(..., description="Reference count")
    status: int = Field(..., description="Status")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class AIProfileTemplateBase(BaseSchema):
    """Base AI profile template schema."""

    name: str = Field(..., max_length=100, description="Template name")
    nickname_template: Optional[str] = Field(
        None, max_length=200, description="Nickname generation template"
    )
    bio_template: Optional[str] = Field(None, description="Bio generation template")
    avatar_template: Optional[str] = Field(None, description="Avatar generation template")
    gender_template: Optional[str] = Field(None, max_length=100, description="Gender assignment template")
    age_template: Optional[str] = Field(None, max_length=100, description="Age assignment template")
    location_template: Optional[str] = Field(
        None, max_length=200, description="Location assignment template"
    )
    json_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema definition")


class AIProfileTemplateCreate(BaseModel):
    """Schema for creating an AI profile template."""

    name: str = Field(..., max_length=100, description="Template name")
    nickname_template: Optional[str] = Field(
        None, max_length=200, description="Nickname generation template"
    )
    bio_template: Optional[str] = Field(None, description="Bio generation template")
    avatar_template: Optional[str] = Field(None, description="Avatar generation template")
    gender_template: Optional[str] = Field(None, max_length=100, description="Gender assignment template")
    age_template: Optional[str] = Field(None, max_length=100, description="Age assignment template")
    location_template: Optional[str] = Field(
        None, max_length=200, description="Location assignment template"
    )
    json_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema definition")


class AIProfileTemplateResponse(AIProfileTemplateBase):
    """Schema for AI profile template response data."""

    usage_count: int = Field(..., description="Reference count")
    status: int = Field(..., description="Status")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")

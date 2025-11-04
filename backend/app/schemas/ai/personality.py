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
    display_name: str = Field(..., max_length=100, description="Display name")
    prompt: str = Field(..., description="Personality prompt template")
    typing_speed: Optional[int] = Field(None, description="Typing speed in characters per minute")
    json_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema definition")


class AIPersonalityCreate(BaseModel):
    """Schema for creating an AI personality."""

    name: str = Field(..., max_length=100, description="Personality name")
    display_name: str = Field(..., max_length=100, description="Display name")
    prompt: str = Field(..., min_length=1, description="Personality prompt template")
    typing_speed: Optional[int] = Field(None, description="Typing speed in characters per minute")
    json_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema definition")


class AIPersonalityUpdate(BaseModel):
    """Schema for updating an AI personality."""

    name: Optional[str] = Field(None, max_length=100, description="Personality name")
    prompt: Optional[str] = Field(None, min_length=1, description="Personality prompt template")
    json_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema definition")
    usage_count: Optional[int] = Field(None, ge=0, description="Reference count")
    status: Optional[int] = Field(
        None, ge=1, le=3, description="Status: 1=active, 2=inactive (follow enum design)"
    )


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
    display_name: Optional[str] = Field(None, max_length=200, description="Display name for UI")
    description: Optional[str] = Field(None, max_length=500, description="Placeholder description")
    example_value: Optional[str] = Field(None, description="Example placeholder value")
    is_required: bool = Field(False, description="Is required")


class AIPersonalityPlaceholderCreate(BaseModel):
    """Schema for creating an AI personality placeholder."""

    personality_id: int = Field(..., description="Personality ID")
    placeholder_key: str = Field(..., max_length=100, description="Placeholder key name")
    display_name: Optional[str] = Field(None, max_length=200, description="Display name for UI")
    description: Optional[str] = Field(None, max_length=500, description="Placeholder description")
    example_value: Optional[str] = Field(None, description="Example placeholder value")
    is_required: bool = Field(False, description="Is required")


class AIPersonalityPlaceholderUpdate(BaseModel):
    """Schema for updating an AI personality placeholder."""

    display_name: Optional[str] = Field(None, max_length=200, description="Display name for UI")
    description: Optional[str] = Field(None, max_length=500, description="Placeholder description")
    example_value: Optional[str] = Field(None, description="Example placeholder value")
    is_required: Optional[bool] = Field(None, description="Is required")


class AIPersonalityPlaceholderResponse(AIPersonalityPlaceholderBase):
    """Schema for AI personality placeholder response data."""

    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# AI Template Schemas


class AICharacterTemplateBase(BaseSchema):
    """Base AI character template schema."""

    name: str = Field(..., max_length=100, description="Template name")
    prompt: str = Field(..., description="Core prompt template")
    json_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema definition")


class AICharacterTemplateCreate(BaseModel):
    """Schema for creating an AI character template."""

    style_id: int = Field(..., description="Style ID, references ai_styles.id")
    personality_id: int = Field(..., description="Personality ID, references ai_personalities.id")
    memory: Optional[str] = Field(None, description="Memory settings")
    display_name: Optional[str] = Field(None, max_length=100, description="Character template display name")
    prompt_variables: Optional[Dict[str, Any]] = Field(
        None, description="Prompt variables/placeholder overrides"
    )
    position_mapping_algorithm: Optional[str] = Field(
        None, max_length=100, description="Position mapping algorithm"
    )
    position_mapping_coefficient: Optional[float] = Field(None, description="Position mapping coefficient")
    is_reusable: bool = Field(True, description="Is reusable: True=reusable, False=single_use")
    profile_id: Optional[int] = Field(None, description="Associated profile template ID (for single-use)")
    status: int = Field(1, ge=1, le=2, description="Status: 1=active, 2=inactive")


class AICharacterTemplateUpdate(BaseModel):
    """Schema for updating an AI character template."""

    style_id: Optional[int] = Field(None, description="Style ID, references ai_styles.id")
    personality_id: Optional[int] = Field(
        None, description="Personality ID, references ai_personalities.id"
    )
    memory: Optional[str] = Field(None, description="Memory settings")
    display_name: Optional[str] = Field(None, max_length=100, description="Character template display name")
    prompt_variables: Optional[Dict[str, Any]] = Field(
        None, description="Prompt variables/placeholder overrides"
    )
    position_mapping_algorithm: Optional[str] = Field(
        None, max_length=100, description="Position mapping algorithm"
    )
    position_mapping_coefficient: Optional[float] = Field(None, description="Position mapping coefficient")
    is_reusable: Optional[bool] = Field(None, description="Is reusable: True=reusable, False=single_use")
    profile_count: Optional[int] = Field(None, ge=0, description="Associated profile template count")
    profile_id: Optional[int] = Field(None, description="Associated profile template ID (for single-use)")
    status: Optional[int] = Field(
        None, ge=1, le=3, description="Status: 1=active, 2=inactive (follow enum design)"
    )


class AICharacterTemplateResponse(AICharacterTemplateBase):
    """Schema for AI character template response data."""

    display_name: Optional[str] = Field(None, description="Character template display name")
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

    category: Optional[str] = Field(None, max_length=50, description="Category")
    character_template_id: int = Field(
        ..., description="Associated character template ID, references ai_character_templates.id"
    )
    nickname: Optional[str] = Field(None, max_length=100, description="Nickname")
    gender: Optional[int] = Field(
        None, ge=1, le=4, description="Gender: 1=male, 2=female, 3=other, 4=unknown"
    )
    avatar_url: Optional[str] = Field(None, max_length=500, description="Avatar URL")
    bio: Optional[str] = Field(None, description="Bio/description")
    region: Optional[str] = Field(None, max_length=100, description="Region/location")
    is_reusable: bool = Field(True, description="Is reusable: True=reusable, False=single_use")
    status: int = Field(1, ge=1, le=2, description="Status: 1=active, 2=inactive")


class AIProfileTemplateUpdate(BaseModel):
    """Schema for updating an AI profile template."""

    category: Optional[str] = Field(None, max_length=50, description="Category")
    character_template_id: Optional[int] = Field(
        None, description="Associated character template ID, references ai_character_templates.id"
    )
    nickname: Optional[str] = Field(None, max_length=100, description="Nickname")
    gender: Optional[int] = Field(
        None, ge=1, le=4, description="Gender: 1=male, 2=female, 3=other, 4=unknown"
    )
    avatar_url: Optional[str] = Field(None, max_length=500, description="Avatar URL")
    bio: Optional[str] = Field(None, description="Bio/description")
    region: Optional[str] = Field(None, max_length=100, description="Region/location")
    is_reusable: Optional[bool] = Field(None, description="Is reusable: True=reusable, False=single_use")
    status: Optional[int] = Field(
        None, ge=1, le=3, description="Status: 1=active, 2=inactive (follow enum design)"
    )


class AIProfileTemplateResponse(AIProfileTemplateBase):
    """Schema for AI profile template response data."""

    usage_count: int = Field(..., description="Reference count")
    status: int = Field(..., description="Status")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")

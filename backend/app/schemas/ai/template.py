"""
AI template schemas.

This module contains Pydantic schemas for AI template-related operations.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class AICharacterTemplateBase(BaseModel):
    """Base schema for AI character template."""

    style_id: int = Field(..., description="Style ID, references ai_styles.id")
    personality_id: int = Field(..., description="Personality ID, references ai_personalities.id")
    memory: Optional[str] = Field(None, description="Memory settings")
    prompt_variables: Optional[Dict[str, Any]] = Field(
        None, description="Prompt variables/placeholder overrides"
    )
    position_mapping_config: Optional[Dict[str, Any]] = Field(
        None, description="Per-dimension position mapping configuration"
    )
    typing_speed_wpm: int = Field(
        ..., ge=1, description="Default typing speed (words per minute) for instantiated characters"
    )
    is_reusable: int = Field(1, description="Is reusable: 1=reusable, 0=single_use")
    profile_count: int = Field(0, description="Associated profile template count")
    profile_id: Optional[int] = Field(None, description="Associated profile template ID (for single-use)")
    status: int = Field(1, description="Status: 1=active, 2=inactive")


class AICharacterTemplateCreate(AICharacterTemplateBase):
    """Schema for creating AI character template."""

    pass


class AICharacterTemplateUpdate(BaseModel):
    """Schema for updating AI character template."""

    style_id: Optional[int] = Field(None, description="Style ID")
    personality_id: Optional[int] = Field(None, description="Personality ID")
    memory: Optional[str] = Field(None, description="Memory settings")
    prompt_variables: Optional[Dict[str, Any]] = Field(None, description="Prompt variables")
    position_mapping_config: Optional[Dict[str, Any]] = Field(
        None, description="Per-dimension position mapping configuration"
    )
    typing_speed_wpm: Optional[int] = Field(
        None,
        ge=1,
        description="Default typing speed (words per minute)",
    )
    is_reusable: Optional[int] = Field(None, description="Is reusable")
    profile_count: Optional[int] = Field(None, description="Profile count")
    profile_id: Optional[int] = Field(None, description="Profile ID")
    status: Optional[int] = Field(None, description="Status")


class AICharacterTemplate(AICharacterTemplateBase):
    """Schema for AI character template response."""

    id: int = Field(..., description="Template ID")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True


class AIProfileTemplateBase(BaseModel):
    """Base schema for AI profile template."""

    category: Optional[str] = Field(None, max_length=50, description="Category")
    character_template_id: int = Field(..., description="Associated character template ID")
    nickname: Optional[str] = Field(None, max_length=100, description="Nickname")
    gender: Optional[int] = Field(None, description="Gender: 1=male, 2=female, 3=other, 4=unknown")
    avatar_url: Optional[str] = Field(None, max_length=500, description="Avatar URL")
    bio: Optional[str] = Field(None, description="Bio/description")
    region: Optional[str] = Field(None, max_length=100, description="Region/location")
    is_reusable: int = Field(1, description="Is reusable: 1=reusable, 0=single_use")
    status: int = Field(1, description="Status: 1=active, 2=inactive")


class AIProfileTemplateCreate(AIProfileTemplateBase):
    """Schema for creating AI profile template."""

    qiao_id: str = Field(..., description="Template external ID")


class AIProfileTemplateUpdate(BaseModel):
    """Schema for updating AI profile template."""

    category: Optional[str] = Field(None, description="Category")
    character_template_id: Optional[int] = Field(None, description="Character template ID")
    nickname: Optional[str] = Field(None, description="Nickname")
    gender: Optional[int] = Field(None, description="Gender")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    bio: Optional[str] = Field(None, description="Bio")
    region: Optional[str] = Field(None, description="Region")
    is_reusable: Optional[int] = Field(None, description="Is reusable")
    status: Optional[int] = Field(None, description="Status")


class AIProfileTemplate(AIProfileTemplateBase):
    """Schema for AI profile template response."""

    id: int = Field(..., description="Template ID")
    qiao_id: str = Field(..., description="Template external ID")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True


class AIRelationshipBase(BaseModel):
    """Base schema for AI relationship."""

    name: str = Field(..., max_length=50, description="Relationship name")
    description: Optional[str] = Field(default=None, description="Relationship description")


class AIRelationshipCreate(AIRelationshipBase):
    """Schema for creating AI relationship."""

    pass


class AIRelationshipUpdate(BaseModel):
    """Schema for updating AI relationship."""

    name: Optional[str] = Field(default=None, description="Relationship name")
    description: Optional[str] = Field(default=None, description="Relationship description")


class AIRelationship(AIRelationshipBase):
    """Schema for AI relationship response."""

    id: int = Field(..., description="Relationship ID")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Update timestamp")

    class Config:
        from_attributes = True

"""
AI template schemas.

This module contains Pydantic schemas for AI template-related operations.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class AIInfoTemplateBase(BaseModel):
    """Base schema for AI info template."""

    style_id: int = Field(default=description="Style ID, references ai_styles.id")
    personality_id: int = Field(default=description="Personality ID, references ai_personalities.id")
    memory: Optional[str] = Field(default=None, description="Memory settings")
    prompt_variables: Optional[Dict[str, Any]] = Field(default=None, description="Prompt variables/placeholder overrides"
    )
    score_offset_algorithm: Optional[str] = Field(default=None, max_length=100, description="Score offset algorithm"
    )
    score_offset_coefficient: Optional[float] = Field(default=None, description="Score offset coefficient")
    is_reusable: int = Field(default=1, description="Is reusable: 1=reusable, 0=single_use")
    profile_count: int = Field(default=0, description="Associated profile template count")
    profile_id: Optional[int] = Field(default=None, description="Associated profile template ID (for single-use)")
    status: int = Field(default=1, description="Status: 1=active, 2=inactive")


class AIInfoTemplateCreate(AIInfoTemplateBase):
    """Schema for creating AI info template."""

    pass


class AIInfoTemplateUpdate(BaseModel):
    """Schema for updating AI info template."""

    style_id: Optional[int] = Field(default=None, description="Style ID")
    personality_id: Optional[int] = Field(default=None, description="Personality ID")
    memory: Optional[str] = Field(default=None, description="Memory settings")
    prompt_variables: Optional[Dict[str, Any]] = Field(default=None, description="Prompt variables")
    score_offset_algorithm: Optional[str] = Field(default=None, description="Score offset algorithm")
    score_offset_coefficient: Optional[float] = Field(default=None, description="Score offset coefficient")
    is_reusable: Optional[int] = Field(default=None, description="Is reusable")
    profile_count: Optional[int] = Field(default=None, description="Profile count")
    profile_id: Optional[int] = Field(default=None, description="Profile ID")
    status: Optional[int] = Field(default=None, description="Status")


class AIInfoTemplate(AIInfoTemplateBase):
    """Schema for AI info template response."""

    id: int = Field(default=description="Template ID")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Update timestamp")

    class Config:
        from_attributes = True


class AIProfileTemplateBase(BaseModel):
    """Base schema for AI profile template."""

    category: Optional[str] = Field(default=None, max_length=50, description="Category")
    info_id: int = Field(default=description="Associated info template ID")
    nickname: Optional[str] = Field(default=None, max_length=100, description="Nickname")
    gender: Optional[int] = Field(default=None, description="Gender: 1=male, 2=female, 3=other, 4=unknown")
    avatar_url: Optional[str] = Field(default=None, max_length=500, description="Avatar URL")
    bio: Optional[str] = Field(default=None, description="Bio/description")
    region: Optional[str] = Field(default=None, max_length=100, description="Region/location")
    is_reusable: int = Field(default=1, description="Is reusable: 1=reusable, 0=single_use")
    status: int = Field(default=1, description="Status: 1=active, 2=inactive")


class AIProfileTemplateCreate(AIProfileTemplateBase):
    """Schema for creating AI profile template."""

    qiao_id: str = Field(default=description="Template external ID")


class AIProfileTemplateUpdate(BaseModel):
    """Schema for updating AI profile template."""

    category: Optional[str] = Field(default=None, description="Category")
    info_id: Optional[int] = Field(default=None, description="Info template ID")
    nickname: Optional[str] = Field(default=None, description="Nickname")
    gender: Optional[int] = Field(default=None, description="Gender")
    avatar_url: Optional[str] = Field(default=None, description="Avatar URL")
    bio: Optional[str] = Field(default=None, description="Bio")
    region: Optional[str] = Field(default=None, description="Region")
    is_reusable: Optional[int] = Field(default=None, description="Is reusable")
    status: Optional[int] = Field(default=None, description="Status")


class AIProfileTemplate(AIProfileTemplateBase):
    """Schema for AI profile template response."""

    id: int = Field(default=description="Template ID")
    qiao_id: str = Field(description="Template external ID")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Update timestamp")

    class Config:
        from_attributes = True


class AIPersonalityPlaceholderBase(BaseModel):
    """Base schema for AI personality placeholder."""

    personality_id: int = Field(default=description="Personality ID")
    placeholder_key: str = Field(max_length=100, description="Placeholder key")
    default_value: Optional[str] = Field(default=None, description="Default value")
    description: Optional[str] = Field(default=None, description="Placeholder description")


class AIPersonalityPlaceholderCreate(AIPersonalityPlaceholderBase):
    """Schema for creating AI personality placeholder."""

    pass


class AIPersonalityPlaceholderUpdate(BaseModel):
    """Schema for updating AI personality placeholder."""

    placeholder_key: Optional[str] = Field(default=None, description="Placeholder key")
    default_value: Optional[str] = Field(default=None, description="Default value")
    description: Optional[str] = Field(default=None, description="Placeholder description")


class AIPersonalityPlaceholder(AIPersonalityPlaceholderBase):
    """Schema for AI personality placeholder response."""

    id: int = Field(default=description="Placeholder ID")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Update timestamp")

    class Config:
        from_attributes = True


class AIRelationshipBase(BaseModel):
    """Base schema for AI relationship."""

    name: str = Field(default=max_length=50, description="Relationship name")
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

    id: int = Field(default=description="Relationship ID")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Update timestamp")

    class Config:
        from_attributes = True


class AIRelationshipIndexBase(BaseModel):
    """Base schema for AI relationship index."""

    style_id: int = Field(default=description="Style ID")
    relationship_id: int = Field(description="Relationship ID")
    min_score: int = Field(description="Minimum score")
    max_score: int = Field(description="Maximum score")


class AIRelationshipIndexCreate(AIRelationshipIndexBase):
    """Schema for creating AI relationship index."""

    pass


class AIRelationshipIndexUpdate(BaseModel):
    """Schema for updating AI relationship index."""

    min_score: Optional[int] = Field(default=None, description="Minimum score")
    max_score: Optional[int] = Field(default=None, description="Maximum score")


class AIRelationshipIndex(AIRelationshipIndexBase):
    """Schema for AI relationship index response."""

    id: int = Field(default=description="Index ID")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Update timestamp")

    class Config:
        from_attributes = True

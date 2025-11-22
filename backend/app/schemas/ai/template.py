"""
AI template schemas.

This module contains Pydantic schemas for AI template-related operations.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class AITypeBase(BaseModel):
    """Base schema for AI type."""

    display_name: str = Field(..., max_length=100, description="Display name (unique)")
    description: Optional[str] = Field(None, description="Description")


class AITypeCreate(AITypeBase):
    """Schema for creating AI type."""

    pass


class AITypeUpdate(BaseModel):
    """Schema for updating AI type."""

    display_name: Optional[str] = Field(None, max_length=100, description="Display name")
    description: Optional[str] = Field(None, description="Description")


class AIType(AITypeBase):
    """AI type response."""

    id: int = Field(..., description="AI type ID")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True


class AITemplateBase(BaseModel):
    """Base schema for AI template."""

    type_id: int = Field(..., description="AI type ID")
    style_id: int = Field(..., description="Style ID, references ai_styles.id")
    personality_id: int = Field(..., description="Personality ID, references ai_personalities.id")
    memory: Optional[str] = Field(None, description="Memory settings")
    prompt_variables: Optional[Dict[str, Any]] = Field(
        None, description="Prompt variables/placeholder overrides"
    )
    position_mapping_config: Optional[Dict[str, Any]] = Field(
        None, description="Per-dimension position mapping configuration"
    )
    timezone: Optional[str] = Field(
        "Asia/Shanghai",
        max_length=50,
        description="Default IANA timezone for instances",
    )
    typing_speed_wpm: int = Field(
        ..., ge=1, description="Default typing speed (words per minute) for instances"
    )
    is_reusable: int = Field(1, description="Is reusable: 1=reusable, 0=single_use")
    status: int = Field(1, description="Status: 1=active, 2=inactive")


class AITemplateCreate(AITemplateBase):
    """Schema for creating AI template."""

    pass


class AITemplateUpdate(BaseModel):
    """Schema for updating AI template."""

    style_id: Optional[int] = Field(None, description="Style ID")
    personality_id: Optional[int] = Field(None, description="Personality ID")
    memory: Optional[str] = Field(None, description="Memory settings")
    prompt_variables: Optional[Dict[str, Any]] = Field(None, description="Prompt variables")
    position_mapping_config: Optional[Dict[str, Any]] = Field(
        None, description="Per-dimension position mapping configuration"
    )
    timezone: Optional[str] = Field(None, description="Default IANA timezone for instances", max_length=50)
    typing_speed_wpm: Optional[int] = Field(
        None,
        ge=1,
        description="Default typing speed (words per minute)",
    )
    is_reusable: Optional[int] = Field(None, description="Is reusable")
    status: Optional[int] = Field(None, description="Status")


class AITemplate(AITemplateBase):
    """Schema for AI template response."""

    id: int = Field(..., description="Template ID")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Update timestamp")
    timezone: str = Field(..., description="Default IANA timezone for instances")

    class Config:
        from_attributes = True


class AIPersonaBase(BaseModel):
    """Base schema for AI persona."""

    type_id: int = Field(..., description="AI type association")
    is_reusable: int = Field(1, description="1=reusable, 0=single_use")
    status: int = Field(1, description="1=active, 2=inactive, 3=used")


class AIPersonaCreate(AIPersonaBase):
    """Schema for creating AI persona."""

    qiao_id: str = Field(..., description="Persona qiao_id")


class AIPersonaUpdate(BaseModel):
    """Schema for updating AI persona."""

    type_id: Optional[int] = Field(None, description="AI type association")
    is_reusable: Optional[int] = Field(None, description="Is reusable flag")
    status: Optional[int] = Field(None, description="Persona status")


class AIPersona(AIPersonaBase):
    """AI persona response."""

    id: int = Field(..., description="Persona ID")
    qiao_id: str = Field(..., description="Persona qiao_id")
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

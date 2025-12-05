"""
AI template schemas.

This module contains Pydantic schemas for AI template-related operations.
"""

from pydantic import BaseModel, Field

from app.core.type_aliases import JSONDict


class AITypeBase(BaseModel):
    """Base schema for AI type."""

    display_name: str = Field(..., max_length=100, description="Display name (unique)")
    description: str | None = Field(None, description="Description")


class AITypeCreate(AITypeBase):
    """Schema for creating AI type."""


class AITypeUpdate(BaseModel):
    """Schema for updating AI type."""

    display_name: str | None = Field(None, max_length=100, description="Display name")
    description: str | None = Field(None, description="Description")


class AIType(AITypeBase):
    """AI type response."""

    id: int = Field(..., description="AI type ID")
    created_at: str | None = Field(None, description="Creation timestamp")
    updated_at: str | None = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True


class AITemplateBase(BaseModel):
    """Base schema for AI template."""

    type_id: int = Field(..., description="AI type ID")
    style_id: int = Field(..., description="Style ID, references ai_styles.id")
    personality_id: int = Field(..., description="Personality ID, references ai_personalities.id")
    memory: str | None = Field(None, description="Memory settings")
    prompt_variables: JSONDict | None = Field(
        None, description="Prompt variables/placeholder overrides"
    )
    position_mapping_config: JSONDict | None = Field(
        None, description="Per-dimension position mapping configuration"
    )
    timezone: str | None = Field(
        "Asia/Shanghai",
        max_length=50,
        description="Default IANA timezone for instances",
    )
    typing_speed_wpm: int = Field(
        ..., ge=1, description="Default typing speed (words per minute) for instances"
    )
    is_reusable: int = Field(1, description="Is reusable: 1=reusable, 0=single_use")
    status: int = Field(1, description="Status: 1=active, 2=inactive")
    llm_config_id: int | None = Field(
        None,
        description="Preferred llm_configs.id for instances created from this template",
    )


class AITemplateCreate(AITemplateBase):
    """Schema for creating AI template."""


class AITemplateUpdate(BaseModel):
    """Schema for updating AI template."""

    style_id: int | None = Field(None, description="Style ID")
    personality_id: int | None = Field(None, description="Personality ID")
    memory: str | None = Field(None, description="Memory settings")
    prompt_variables: JSONDict | None = Field(None, description="Prompt variables")
    position_mapping_config: JSONDict | None = Field(
        None, description="Per-dimension position mapping configuration"
    )
    timezone: str | None = Field(
        None, description="Default IANA timezone for instances", max_length=50
    )
    typing_speed_wpm: int | None = Field(
        None,
        ge=1,
        description="Default typing speed (words per minute)",
    )
    is_reusable: int | None = Field(None, description="Is reusable")
    status: int | None = Field(None, description="Status")
    llm_config_id: int | None = Field(
        None, description="Preferred llm_configs.id for this template"
    )


class AITemplate(AITemplateBase):
    """Schema for AI template response."""

    id: int = Field(..., description="Template ID")
    created_at: str | None = Field(None, description="Creation timestamp")
    updated_at: str | None = Field(None, description="Update timestamp")
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

    type_id: int | None = Field(None, description="AI type association")
    is_reusable: int | None = Field(None, description="Is reusable flag")
    status: int | None = Field(None, description="Persona status")


class AIPersona(AIPersonaBase):
    """AI persona response."""

    id: int = Field(..., description="Persona ID")
    qiao_id: str = Field(..., description="Persona qiao_id")
    created_at: str | None = Field(None, description="Creation timestamp")
    updated_at: str | None = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True

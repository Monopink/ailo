"""
AI style related schemas.

This module contains Pydantic schemas for AI styles and relationships.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

from schemas.common import BaseSchema


# AI Style Schemas


class AIStyleBase(BaseSchema):
    """Base AI style schema."""

    name: str = Field(..., max_length=100, description="Style name")
    score_count: int = Field(..., description="Number of scoring dimensions")
    score_name: List[str] = Field(..., description="Scoring dimension names")


class AIStyleCreate(BaseModel):
    """Schema for creating an AI style."""

    name: str = Field(..., max_length=100, description="Style name")
    score_count: int = Field(..., ge=1, le=10, description="Number of scoring dimensions")
    score_name: List[str] = Field(..., min_items=1, max_items=10, description="Scoring dimension names")

    @field_validator("score_name")
    @classmethod
    def validate_score_name_count(cls, v, info):
        """Validate score_name count matches score_count."""
        if info.data and "score_count" in info.data:
            score_count = info.data["score_count"]
            if len(v) != score_count:
                raise ValueError("score_name length must match score_count")
        return v


class AIStyleUpdate(BaseModel):
    """Schema for updating an AI style."""

    name: Optional[str] = Field(None, max_length=100, description="Style name")
    score_count: Optional[int] = Field(None, ge=1, le=10, description="Number of scoring dimensions")
    score_name: Optional[List[str]] = Field(
        None, min_items=1, max_items=10, description="Scoring dimension names"
    )
    usage_count: Optional[int] = Field(None, ge=0, description="Reference count")
    status: Optional[int] = Field(None, ge=1, le=2, description="Status: 1=active, 2=inactive")


class AIStyleResponse(AIStyleBase):
    """Schema for AI style response data."""

    usage_count: int = Field(..., description="Reference count")
    status: int = Field(..., description="Status")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# AI Relationship Schemas


class AIRelationshipBase(BaseSchema):
    """Base AI relationship schema."""

    name: str = Field(..., max_length=100, description="Relationship name")
    description: str = Field(..., max_length=500, description="Relationship description")


class AIRelationshipCreate(BaseModel):
    """Schema for creating an AI relationship."""

    name: str = Field(..., max_length=100, description="Relationship name")
    prompt_fragment: Optional[str] = Field(None, description="Prompt fragment for this relationship")


class AIRelationshipUpdate(BaseModel):
    """Schema for updating an AI relationship."""

    name: Optional[str] = Field(None, max_length=100, description="Relationship name")
    prompt_fragment: Optional[str] = Field(None, description="Prompt fragment for this relationship")
    status: Optional[int] = Field(None, description="Status")


class AIRelationshipResponse(AIRelationshipBase):
    """Schema for AI relationship response data."""

    usage_count: int = Field(..., description="Usage count")
    status: int = Field(..., description="Status")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# AI Relationship Index Schemas


class AIRelationshipIndexBase(BaseSchema):
    """Base AI relationship index schema."""

    style_id: int = Field(..., description="Style ID")
    score_order: int = Field(..., description="Score dimension order")
    score_start: int = Field(..., description="Score range start")
    score_end: int = Field(..., description="Score range end")
    relationship_id: int = Field(..., description="Relationship ID")


class AIRelationshipIndexCreate(BaseModel):
    """Schema for creating an AI relationship index."""

    style_id: int = Field(..., description="Style ID")
    score_order: int = Field(..., description="Score dimension order")
    score_start: int = Field(..., ge=0, le=1000, description="Score range start")
    score_end: int = Field(..., ge=0, le=1000, description="Score range end")
    relationship_id: int = Field(..., description="Relationship ID")

    @field_validator("score_end")
    @classmethod
    def validate_score_range(cls, v, info):
        """Validate score_end is greater than score_start."""
        if info.data and "score_start" in info.data:
            score_start = info.data["score_start"]
            if v <= score_start:
                raise ValueError("score_end must be greater than score_start")
        return v


class AIRelationshipIndexUpdate(BaseModel):
    """Schema for updating an AI relationship index."""

    score_order: Optional[int] = Field(None, description="Score dimension order")
    score_name: Optional[str] = Field(None, max_length=100, description="Score name")
    start_position: Optional[int] = Field(
        None, ge=0, le=1000, description="Start position, 0-1000 per mille"
    )
    end_position: Optional[int] = Field(None, ge=0, le=1000, description="End position, 0-1000 per mille")
    relationship_id: Optional[int] = Field(None, description="Relationship ID")
    priority: Optional[int] = Field(None, description="Priority level")
    limit_count: Optional[int] = Field(None, description="Maximum occurrence count, NULL means unlimited")

    @field_validator("end_position")
    @classmethod
    def validate_score_range(cls, v, info):
        """Validate end_position is greater than start_position."""
        if v is not None and info.data and "start_position" in info.data:
            start_position = info.data["start_position"]
            if start_position is not None and v <= start_position:
                raise ValueError("end_position must be greater than start_position")
        return v


class AIRelationshipIndexResponse(AIRelationshipIndexBase):
    """Schema for AI relationship index response data."""

    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")

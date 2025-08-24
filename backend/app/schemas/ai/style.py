"""
AI style related schemas.

This module contains Pydantic schemas for AI styles and relationships.
"""

from datetime import datetime
from typing import List
from pydantic import BaseModel, Field, validator

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

    @validator("score_name")
    def validate_score_name_count(cls, v, values):
        """Validate score_name count matches score_count."""
        score_count = values.get("score_count")
        if score_count and len(v) != score_count:
            raise ValueError("score_name length must match score_count")
        return v


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
    description: str = Field(..., max_length=500, description="Relationship description")


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

    @validator("score_end")
    def validate_score_range(cls, v, values):
        """Validate score_end is greater than score_start."""
        score_start = values.get("score_start")
        if score_start is not None and v <= score_start:
            raise ValueError("score_end must be greater than score_start")
        return v


class AIRelationshipIndexResponse(AIRelationshipIndexBase):
    """Schema for AI relationship index response data."""

    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")

"""Shared AI service data structures.

Defines strict TypedDict models used across AI services to keep
instance-related data consistent and detached from ORM objects.
"""

from __future__ import annotations

from typing import TypedDict

from app.core.type_aliases import JSONDict


class StyleInfo(TypedDict):
    """Style metadata exposed to AI services."""

    id: int
    display_name: str


class PersonalityInfo(TypedDict):
    """Personality metadata and prompt template."""

    id: int
    display_name: str
    prompt: str
    status: int
    json_schema: JSONDict | None


class ProfileInfo(TypedDict):
    """Profile fields mirrored from profile table."""

    nickname: str
    bio: str | None
    gender: int | None
    avatar_url: str | None
    avatar_prompt: str | None
    region: str | None


class AITypeInfo(TypedDict):
    """AI type metadata used in instance context."""

    id: int
    display_name: str


class DimensionSpec(TypedDict):
    """Dimension definition for schema generation and scoring."""

    id: int
    name: str
    display_name: str
    initial_position: int


class CurrentRelationship(TypedDict):
    """Currently selected relationship metadata."""

    id: int
    display_name: str
    prompt_fragment: str


RelationshipCounts = dict[str, int]


class InstanceContext(TypedDict):
    """Single source of truth for AI instance runtime context."""

    # Core identifiers
    instance_id: int
    instance_qiao_id: str
    user_id: int
    user_qiao_id: str
    ai_type: AITypeInfo | None
    status: int
    created_by: int
    llm_config_id: int | None

    # Prompt + runtime configuration
    prompt_variables: JSONDict
    request_params: JSONDict
    typing_speed_wpm: int
    timezone: str
    created_from_profile_qiao_id: str | None

    # Relationship state
    relationship_id: int | None
    relationship_counts: RelationshipCounts

    # Linked metadata
    style: StyleInfo
    personality: PersonalityInfo
    profile: ProfileInfo
    current_relationship: CurrentRelationship | None

    # Derived collections
    dimensions: list[DimensionSpec]


__all__ = [
    "AITypeInfo",
    "CurrentRelationship",
    "DimensionSpec",
    "InstanceContext",
    "PersonalityInfo",
    "ProfileInfo",
    "RelationshipCounts",
    "StyleInfo",
]

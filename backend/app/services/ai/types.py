"""Shared AI service data structures.

Defines strict TypedDict models used across AI services to keep
character-related data consistent and detached from ORM objects.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class StyleInfo(TypedDict):
    """Style metadata exposed to AI services."""

    id: int
    name: str
    display_name: str


class PersonalityInfo(TypedDict):
    """Personality metadata and prompt template."""

    id: int
    name: str
    display_name: str
    prompt: str
    status: int
    json_schema: Optional[Dict[str, Any]]


class ProfileInfo(TypedDict):
    """Profile fields mirrored from profile table."""

    nickname: str
    bio: Optional[str]
    gender: Optional[int]
    avatar_url: Optional[str]
    avatar_prompt: Optional[str]
    region: Optional[str]


class DimensionSpec(TypedDict):
    """Dimension definition for schema generation and scoring."""

    id: int
    name: str
    display_name: str
    initial_position: int


class CurrentRelationship(TypedDict):
    """Currently selected relationship metadata."""

    id: int
    name: str
    display_name: str
    prompt_fragment: str


RelationshipCounts = Dict[str, int]


class CharacterContext(TypedDict):
    """Single source of truth for AI character runtime context."""

    # Core identifiers
    character_id: int
    character_qiao_id: str
    category: Optional[str]
    status: int
    created_by: int

    # Prompt + runtime configuration
    memory: Optional[str]
    prompt_variables: Dict[str, Any]
    request_params: Dict[str, Any]
    typing_speed_wpm: int
    timezone: str
    created_from_profile_qiao_id: Optional[str]

    # Relationship state
    relationship_id: Optional[int]
    relationship_counts: RelationshipCounts

    # Linked metadata
    style: StyleInfo
    personality: PersonalityInfo
    profile: ProfileInfo
    current_relationship: Optional[CurrentRelationship]

    # Derived collections
    dimensions: List[DimensionSpec]


__all__ = [
    "CharacterContext",
    "CurrentRelationship",
    "DimensionSpec",
    "PersonalityInfo",
    "ProfileInfo",
    "RelationshipCounts",
    "StyleInfo",
]

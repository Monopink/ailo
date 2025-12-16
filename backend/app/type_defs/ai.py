"""
Shared AI service data structures.

Defines strict TypedDict models used across AI services to keep
instance-related data consistent and detached from ORM objects.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict

from app.type_defs.common import JSONDict

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from app.models.ai.style import AIRelationship


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


class RelationshipScoreEntry(TypedDict):
    """Stored relationship score entry."""

    id: int
    instance_id: int
    dimension_id: int
    dimension_name: str
    dimension_display_name: str
    score: int
    position: int
    initial_position: int
    created_at: NotRequired[datetime]
    updated_at: NotRequired[datetime]


class InstanceDimensionData(TypedDict):
    """Instance dimension data with mapping configuration from get_by_instance query."""

    dimension_id: int
    dimension_name: str
    score: int
    position: int
    position_mapping_algorithm: int
    position_mapping_params: JSONDict
    initial_position: int


class RelationshipCandidate(TypedDict):
    """Candidate relationship mapping for selection."""

    relationship_id: int
    relationship_display_name: str | None
    prompt_fragment: str | None
    priority: int
    start_position: int
    end_position: int
    limit_count: int


class RelationshipMapping(TypedDict):
    """Detailed mapping used during score evaluation."""

    relationship: AIRelationship
    dimension_name: str
    start_position: int
    end_position: int
    priority: int
    limit_count: int | None


class RelationshipTiming(TypedDict):
    """Wake/scheduling configuration derived from relationship settings."""

    wake_time_min_ms: int
    wake_time_max_ms: int
    wake_time_bias: str
    wake_window_ms: int
    wake_time_adjustment: str
    no_reply_probability: float
    followup_delay_ms: int


class InstanceContext(TypedDict):
    """AI instance runtime context - constructed in `get_instance_context` only."""

    # Core identifiers
    instance_id: int
    instance_qiao_id: str
    user_id: int
    user_qiao_id: str
    status: int
    created_by: int

    # Dynamic attributes
    prompt_variables: JSONDict
    request_params: JSONDict
    typing_speed_wpm: int
    timezone: str

    # Relationship state
    relationship_counts: RelationshipCounts

    # Linked metadata
    style: StyleInfo
    personality: PersonalityInfo
    profile: ProfileInfo

    # Derived collections
    dimensions: list[DimensionSpec]

    # Optional / nullable fields
    ai_type: NotRequired[AITypeInfo | None]
    llm_config_id: NotRequired[int | None]
    created_from_profile_qiao_id: NotRequired[str | None]
    relationship_id: NotRequired[int | None]
    current_relationship: NotRequired[CurrentRelationship | None]


class AlgorithmParameterSpec(TypedDict):
    """UI/validation metadata for algorithm parameters."""

    name: str
    label: str
    description: str
    input_type: Literal["integer", "float"]
    min: float | None
    max: float | None
    step: float | None
    required: bool


class V1Params(TypedDict):
    """Typed representation for V1 algorithm parameters."""

    left_sensitivity: float
    right_sensitivity: float
    left_positive_gain: float
    left_negative_gain: float
    right_positive_gain: float
    right_negative_gain: float


__all__ = [
    "AITypeInfo",
    "AlgorithmParameterSpec",
    "CurrentRelationship",
    "DimensionSpec",
    "InstanceContext",
    "InstanceDimensionData",
    "PersonalityInfo",
    "ProfileInfo",
    "RelationshipCandidate",
    "RelationshipCounts",
    "RelationshipMapping",
    "RelationshipScoreEntry",
    "RelationshipTiming",
    "StyleInfo",
    "V1Params",
]

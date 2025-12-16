"""
Central export module for shared backend type definitions.

Modules should import TypedDicts and aliases from here instead of touching
service-specific files, ensuring type contracts stay consistent.
"""

from app.type_defs.admin import AIInstanceTestContext, AIInstanceTestResponse
from app.type_defs.ai import (
    AITypeInfo,
    AlgorithmParameterSpec,
    CurrentRelationship,
    DimensionSpec,
    InstanceContext,
    InstanceDimensionData,
    PersonalityInfo,
    ProfileInfo,
    RelationshipCandidate,
    RelationshipCounts,
    RelationshipMapping,
    RelationshipScoreEntry,
    RelationshipTiming,
    StyleInfo,
    V1Params,
)
from app.type_defs.common import JSONArray, JSONDict, JSONPrimitive, JSONValue, SnowflakeComponents
from app.type_defs.llm import (
    LLMCachingOptions,
    LLMProviderResult,
    LLMRequestOptions,
    LLMSessionContext,
    LLMStreamingDecision,
    PreemptionChecker,
    ProviderMessage,
    ProviderTool,
)
from app.type_defs.system import ConfigGroup

__all__ = [
    # Admin types
    "AIInstanceTestContext",
    "AIInstanceTestResponse",
    "AITypeInfo",
    "AlgorithmParameterSpec",
    # System types
    "ConfigGroup",
    "CurrentRelationship",
    "DimensionSpec",
    "InstanceContext",
    "InstanceDimensionData",
    "JSONArray",
    "JSONDict",
    # Common JSON aliases
    "JSONPrimitive",
    "JSONValue",
    "LLMCachingOptions",
    "LLMProviderResult",
    "LLMRequestOptions",
    "LLMSessionContext",
    "LLMStreamingDecision",
    "PersonalityInfo",
    "PreemptionChecker",
    "ProfileInfo",
    # LLM types
    "ProviderMessage",
    "ProviderTool",
    "RelationshipCandidate",
    "RelationshipCounts",
    "RelationshipMapping",
    "RelationshipScoreEntry",
    "RelationshipTiming",
    "SnowflakeComponents",
    # AI service types
    "StyleInfo",
    "V1Params",
]

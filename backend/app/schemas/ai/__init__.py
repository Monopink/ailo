"""
AI system schemas module.

This module imports all AI-related Pydantic schemas.
"""

# Chat schemas
from .chat import AIChatRequest, AIChatResponse

# Instance schemas
from .instance import (
    AIInstanceBase,
    AIInstanceCreate,
    AIInstanceListResponse,
    AIInstanceResponse,
    AIInstanceUpdate,
    BatchAIInstanceDelete,
)

# Log schemas
from .log import (
    AIInstanceStats,
    AIRequestLogBase,
    AIRequestLogCreate,
    AIRequestLogResponse,
    AIRequestLogUpdate,
    AISystemStats,
    AIUserStats,
)
from .memory import (
    AIInstanceMemory,
    AIInstanceMemoryCreate,
    AIInstanceMemoryUpdate,
    AITemplateMemory,
    AITemplateMemoryCreate,
    AITemplateMemoryUpdate,
)

# Personality schemas
from .personality import (
    AIPersonalityBase,
    AIPersonalityCreate,
    AIPersonalityPlaceholderBase,
    AIPersonalityPlaceholderCreate,
    AIPersonalityPlaceholderResponse,
    AIPersonalityPlaceholderUpdate,
    AIPersonalityResponse,
    AIPersonalityUpdate,
)

# Style schemas (dimensions, style-dimension junctions, relationships, mappings)
from .style import (
    AIDimensionBase,
    AIDimensionCreate,
    AIDimensionRelationshipMappingBase,
    AIDimensionRelationshipMappingCreate,
    AIDimensionRelationshipMappingResponse,
    AIDimensionRelationshipMappingUpdate,
    AIDimensionResponse,
    AIDimensionUpdate,
    AIRelationshipBase,
    AIRelationshipCreate,
    AIRelationshipResponse,
    AIStyleBase,
    AIStyleCreate,
    AIStyleDimensionBase,
    AIStyleDimensionCreate,
    AIStyleDimensionResponse,
    AIStyleDimensionUpdate,
    AIStyleResponse,
    AIStyleUpdate,
    DimensionScoreRange,
    RelationshipMappingDetail,
    RelationshipMappingWithDimension,
    StyleWithRelationships,
)
from .template import AIPersona as AIPersonaResponse
from .template import (
    AIPersonaBase,
    AIPersonaCreate,
    AIPersonaUpdate,
    AITemplateBase,
    AITemplateCreate,
    AITemplateUpdate,
    AITypeBase,
    AITypeCreate,
    AITypeUpdate,
)
from .template import AITemplate as AITemplateResponse
from .template import AIType as AITypeResponse

# Export all AI schemas
__all__ = [
    # Instance
    "AIInstanceBase",
    "AIInstanceCreate",
    "AIInstanceUpdate",
    "AIInstanceResponse",
    "AIInstanceListResponse",
    "BatchAIInstanceDelete",
    # Chat
    "AIChatRequest",
    "AIChatResponse",
    # Memory
    "AIInstanceMemory",
    "AIInstanceMemoryCreate",
    "AIInstanceMemoryUpdate",
    "AITemplateMemory",
    "AITemplateMemoryCreate",
    "AITemplateMemoryUpdate",
    # Style
    "AIStyleBase",
    "AIStyleCreate",
    "AIStyleUpdate",
    "AIStyleResponse",
    "StyleWithRelationships",
    "AIDimensionBase",
    "AIDimensionCreate",
    "AIDimensionUpdate",
    "AIDimensionResponse",
    "DimensionScoreRange",
    "AIStyleDimensionBase",
    "AIStyleDimensionCreate",
    "AIStyleDimensionUpdate",
    "AIStyleDimensionResponse",
    "AIRelationshipBase",
    "AIRelationshipCreate",
    "AIRelationshipResponse",
    "AIDimensionRelationshipMappingBase",
    "AIDimensionRelationshipMappingCreate",
    "AIDimensionRelationshipMappingUpdate",
    "AIDimensionRelationshipMappingResponse",
    "RelationshipMappingDetail",
    "RelationshipMappingWithDimension",
    # Personality
    "AIPersonalityBase",
    "AIPersonalityCreate",
    "AIPersonalityUpdate",
    "AIPersonalityResponse",
    "AIPersonalityPlaceholderBase",
    "AIPersonalityPlaceholderCreate",
    "AIPersonalityPlaceholderUpdate",
    "AIPersonalityPlaceholderResponse",
    # Template
    "AITypeBase",
    "AITypeCreate",
    "AITypeUpdate",
    "AITypeResponse",
    "AITemplateBase",
    "AITemplateCreate",
    "AITemplateUpdate",
    "AITemplateResponse",
    "AIPersonaBase",
    "AIPersonaCreate",
    "AIPersonaUpdate",
    "AIPersonaResponse",
    # Log
    "AIRequestLogBase",
    "AIRequestLogCreate",
    "AIRequestLogUpdate",
    "AIRequestLogResponse",
    "AIInstanceStats",
    "AIUserStats",
    "AISystemStats",
]

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
    "AIChatRequest",
    "AIChatResponse",
    "AIDimensionBase",
    "AIDimensionCreate",
    "AIDimensionRelationshipMappingBase",
    "AIDimensionRelationshipMappingCreate",
    "AIDimensionRelationshipMappingResponse",
    "AIDimensionRelationshipMappingUpdate",
    "AIDimensionResponse",
    "AIDimensionUpdate",
    "AIInstanceBase",
    "AIInstanceCreate",
    "AIInstanceListResponse",
    "AIInstanceMemory",
    "AIInstanceMemoryCreate",
    "AIInstanceMemoryUpdate",
    "AIInstanceResponse",
    "AIInstanceStats",
    "AIInstanceUpdate",
    "AIPersonaBase",
    "AIPersonaCreate",
    "AIPersonaResponse",
    "AIPersonaUpdate",
    "AIPersonalityBase",
    "AIPersonalityCreate",
    "AIPersonalityPlaceholderBase",
    "AIPersonalityPlaceholderCreate",
    "AIPersonalityPlaceholderResponse",
    "AIPersonalityPlaceholderUpdate",
    "AIPersonalityResponse",
    "AIPersonalityUpdate",
    "AIRelationshipBase",
    "AIRelationshipCreate",
    "AIRelationshipResponse",
    "AIRequestLogBase",
    "AIRequestLogCreate",
    "AIRequestLogResponse",
    "AIRequestLogUpdate",
    "AIStyleBase",
    "AIStyleCreate",
    "AIStyleDimensionBase",
    "AIStyleDimensionCreate",
    "AIStyleDimensionResponse",
    "AIStyleDimensionUpdate",
    "AIStyleResponse",
    "AIStyleUpdate",
    "AISystemStats",
    "AITemplateBase",
    "AITemplateCreate",
    "AITemplateMemory",
    "AITemplateMemoryCreate",
    "AITemplateMemoryUpdate",
    "AITemplateResponse",
    "AITemplateUpdate",
    "AITypeBase",
    "AITypeCreate",
    "AITypeResponse",
    "AITypeUpdate",
    "AIUserStats",
    "BatchAIInstanceDelete",
]

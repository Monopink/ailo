"""
AI system schemas module.

This module imports all AI-related Pydantic schemas.
"""

# Instance schemas
from .instance import (
    AIInstanceBase,
    AIInstanceCreate,
    AIInstanceUpdate,
    AIInstanceResponse,
    AIInstanceListResponse,
    BatchAIInstanceDelete,
)

# Chat schemas
from .chat import (
    AIChatRequest,
    AIChatResponse,
)

# Style schemas
from .style import (
    AIStyleBase,
    AIStyleCreate,
    AIStyleUpdate,
    AIStyleResponse,
    # Dimensions
    AIDimensionBase,
    AIDimensionCreate,
    AIDimensionUpdate,
    AIDimensionResponse,
    # Style-dimension junction
    AIStyleDimensionBase,
    AIStyleDimensionCreate,
    AIStyleDimensionUpdate,
    AIStyleDimensionResponse,
    # Relationships
    AIRelationshipBase,
    AIRelationshipCreate,
    AIRelationshipUpdate,
    AIRelationshipResponse,
    # Dimension relationship mappings
    AIDimensionRelationshipMappingBase,
    AIDimensionRelationshipMappingCreate,
    AIDimensionRelationshipMappingUpdate,
    AIDimensionRelationshipMappingResponse,
)

# Personality schemas
from .personality import (
    AIPersonalityBase,
    AIPersonalityCreate,
    AIPersonalityUpdate,
    AIPersonalityResponse,
    AIPersonalityPlaceholderBase,
    AIPersonalityPlaceholderCreate,
    AIPersonalityPlaceholderUpdate,
    AIPersonalityPlaceholderResponse,
)
from .template import (
    AITypeBase,
    AITypeCreate,
    AITypeUpdate,
    AIType as AITypeResponse,
    AITemplateBase,
    AITemplateCreate,
    AITemplateUpdate,
    AITemplate as AITemplateResponse,
    AIPersonaBase,
    AIPersonaCreate,
    AIPersonaUpdate,
    AIPersona as AIPersonaResponse,
)

# Log schemas
from .log import (
    AIRequestLogBase,
    AIRequestLogCreate,
    AIRequestLogUpdate,
    AIRequestLogResponse,
    AIInstanceStats,
    AIUserStats,
    AISystemStats,
)

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
    # Style
    "AIStyleBase",
    "AIStyleCreate",
    "AIStyleUpdate",
    "AIStyleResponse",
    "AIDimensionBase",
    "AIDimensionCreate",
    "AIDimensionUpdate",
    "AIDimensionResponse",
    "AIStyleDimensionBase",
    "AIStyleDimensionCreate",
    "AIStyleDimensionUpdate",
    "AIStyleDimensionResponse",
    "AIRelationshipBase",
    "AIRelationshipCreate",
    "AIRelationshipUpdate",
    "AIRelationshipResponse",
    "AIDimensionRelationshipMappingBase",
    "AIDimensionRelationshipMappingCreate",
    "AIDimensionRelationshipMappingUpdate",
    "AIDimensionRelationshipMappingResponse",
    # Personality
    "AIPersonalityBase",
    "AIPersonalityCreate",
    "AIPersonalityUpdate",
    "AIPersonalityResponse",
    "AIPersonalityPlaceholderBase",
    "AIPersonalityPlaceholderCreate",
    "AIPersonalityPlaceholderUpdate",
    "AIPersonalityPlaceholderResponse",
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

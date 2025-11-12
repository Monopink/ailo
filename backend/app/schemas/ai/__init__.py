"""
AI system schemas module.

This module imports all AI-related Pydantic schemas.
"""

# Character schemas
from .character import (
    AICharacterBase,
    AICharacterCreate,
    AICharacterUpdate,
    AICharacterResponse,
    AICharacterListResponse,
    BatchAICharacterDelete,
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
    AIProfileTemplateBase,
    AIProfileTemplateCreate,
    AIProfileTemplateUpdate,
    AIProfileTemplateResponse,
)
from .template import (
    AICharacterTemplateBase,
    AICharacterTemplateCreate,
    AICharacterTemplateUpdate,
    AICharacterTemplate as AICharacterTemplateResponse,
)

# Log schemas
from .log import (
    AIRequestLogBase,
    AIRequestLogCreate,
    AIRequestLogUpdate,
    AIRequestLogResponse,
    AICharacterStats,
    AIUserStats,
    AISystemStats,
)

# Export all AI schemas
__all__ = [
    # Character
    "AICharacterBase",
    "AICharacterCreate",
    "AICharacterUpdate",
    "AICharacterResponse",
    "AICharacterListResponse",
    "BatchAICharacterDelete",
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
    "AICharacterTemplateBase",
    "AICharacterTemplateCreate",
    "AICharacterTemplateUpdate",
    "AICharacterTemplateResponse",
    "AIProfileTemplateBase",
    "AIProfileTemplateCreate",
    "AIProfileTemplateUpdate",
    "AIProfileTemplateResponse",
    # Log
    "AIRequestLogBase",
    "AIRequestLogCreate",
    "AIRequestLogUpdate",
    "AIRequestLogResponse",
    "AICharacterStats",
    "AIUserStats",
    "AISystemStats",
]

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
    AIContextBase,
    AIContextCreate,
    AIContextUpdate,
    AIContextResponse,
    BatchAICharacterDelete,
)

# Chat schemas
from .chat import (
    AIChatRequest,
    AIChatResponse,
    AIRelationshipScoreResponse,
    AIRelationshipScoreUpdate,
)

# Style schemas
from .style import (
    AIStyleBase,
    AIStyleCreate,
    AIStyleUpdate,
    AIStyleResponse,
    AIRelationshipDimensionBase,
    AIRelationshipDimensionCreate,
    AIRelationshipDimensionUpdate,
    AIRelationshipDimensionResponse,
    AIRelationshipBase,
    AIRelationshipCreate,
    AIRelationshipUpdate,
    AIRelationshipResponse,
    AIRelationshipIndexBase,
    AIRelationshipIndexCreate,
    AIRelationshipIndexUpdate,
    AIRelationshipIndexResponse,
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
    AIInfoTemplateBase,
    AIInfoTemplateCreate,
    AIInfoTemplateUpdate,
    AIInfoTemplateResponse,
    AIProfileTemplateBase,
    AIProfileTemplateCreate,
    AIProfileTemplateUpdate,
    AIProfileTemplateResponse,
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
    "AIContextBase",
    "AIContextCreate",
    "AIContextUpdate",
    "AIContextResponse",
    "BatchAICharacterDelete",
    # Chat
    "AIChatRequest",
    "AIChatResponse",
    "AIRelationshipScoreResponse",
    "AIRelationshipScoreUpdate",
    # Style
    "AIStyleBase",
    "AIStyleCreate",
    "AIStyleUpdate",
    "AIStyleResponse",
    "AIRelationshipDimensionBase",
    "AIRelationshipDimensionCreate",
    "AIRelationshipDimensionUpdate",
    "AIRelationshipDimensionResponse",
    "AIRelationshipBase",
    "AIRelationshipCreate",
    "AIRelationshipUpdate",
    "AIRelationshipResponse",
    "AIRelationshipIndexBase",
    "AIRelationshipIndexCreate",
    "AIRelationshipIndexUpdate",
    "AIRelationshipIndexResponse",
    # Personality
    "AIPersonalityBase",
    "AIPersonalityCreate",
    "AIPersonalityUpdate",
    "AIPersonalityResponse",
    "AIPersonalityPlaceholderBase",
    "AIPersonalityPlaceholderCreate",
    "AIPersonalityPlaceholderUpdate",
    "AIPersonalityPlaceholderResponse",
    "AIInfoTemplateBase",
    "AIInfoTemplateCreate",
    "AIInfoTemplateUpdate",
    "AIInfoTemplateResponse",
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

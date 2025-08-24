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
    AIStyleResponse,
    AIRelationshipBase,
    AIRelationshipCreate,
    AIRelationshipResponse,
    AIRelationshipIndexBase,
    AIRelationshipIndexCreate,
    AIRelationshipIndexResponse,
)

# Personality schemas
from .personality import (
    AIPersonalityBase,
    AIPersonalityCreate,
    AIPersonalityResponse,
    AIPersonalityPlaceholderBase,
    AIPersonalityPlaceholderCreate,
    AIPersonalityPlaceholderResponse,
    AIInfoTemplateBase,
    AIInfoTemplateCreate,
    AIInfoTemplateResponse,
    AIProfileTemplateBase,
    AIProfileTemplateCreate,
    AIProfileTemplateResponse,
)

# Log schemas
from .log import (
    AIRequestLogBase,
    AIRequestLogCreate,
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
    "AIStyleResponse",
    "AIRelationshipBase",
    "AIRelationshipCreate",
    "AIRelationshipResponse",
    "AIRelationshipIndexBase",
    "AIRelationshipIndexCreate",
    "AIRelationshipIndexResponse",
    # Personality
    "AIPersonalityBase",
    "AIPersonalityCreate",
    "AIPersonalityResponse",
    "AIPersonalityPlaceholderBase",
    "AIPersonalityPlaceholderCreate",
    "AIPersonalityPlaceholderResponse",
    "AIInfoTemplateBase",
    "AIInfoTemplateCreate",
    "AIInfoTemplateResponse",
    "AIProfileTemplateBase",
    "AIProfileTemplateCreate",
    "AIProfileTemplateResponse",
    # Log
    "AIRequestLogBase",
    "AIRequestLogCreate",
    "AIRequestLogResponse",
    "AICharacterStats",
    "AIUserStats",
    "AISystemStats",
]

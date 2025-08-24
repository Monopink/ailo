"""
AI system models module.

This module imports all AI-related SQLAlchemy models.
"""

# Character and context models
from .character import AICharacter, AIContext

# Template models
from .template import AIInfoTemplate, AIProfileTemplate

# Personality models
from .personality import AIPersonality, AIPersonalityPlaceholder

# Style and relationship models
from .style import AIStyle, AIRelationship, AIRelationshipIndex

# Score models
from .score import AIRelationshipScore, AIRelationshipCount

# Log models
from .log import AIRequestLog

# Export all AI models
__all__ = [
    # Character and context
    "AICharacter",
    "AIContext",
    # Templates
    "AIInfoTemplate",
    "AIProfileTemplate",
    # Personality
    "AIPersonality",
    "AIPersonalityPlaceholder",
    # Style and relationship
    "AIStyle",
    "AIRelationship",
    "AIRelationshipIndex",
    # Score
    "AIRelationshipScore",
    "AIRelationshipCount",
    # Log
    "AIRequestLog",
]

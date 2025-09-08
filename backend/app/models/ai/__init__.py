"""
AI system models module.

This module imports all AI-related SQLAlchemy models.
"""

# Character and context models
from .character import AICharacter, AIContext, AIContextArchive

# Template models
from .template import AIInfoTemplate, AIProfileTemplate

# Personality models
from .personality import AIPersonality, AIPersonalityPlaceholder

# Style and relationship models
from .style import AIStyle, AIRelationship, AIRelationshipIndex, AIRelationshipDimension

# Score models
from .score import AIRelationshipScore

# Log models
from .log import AIRequestLog

# Export all AI models
__all__ = [
    # Character and context
    "AICharacter",
    "AIContext",
    "AIContextArchive",
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
    "AIRelationshipDimension",
    # Score
    "AIRelationshipScore",
    # Log
    "AIRequestLog",
]

"""
AI system models module.

This module imports all AI-related SQLAlchemy models.
"""

# Character and conversation models
from .character import (
    AICharacter,
    AIMessageBuffer,
    AIConversationItem,
    AIConversationItemArchive,
    AIConversationState,
)

# Template models
from .template import AICharacterTemplate, AIProfileTemplate

# Personality models
from .personality import AIPersonality, AIPersonalityPlaceholder

# Style and relationship models
from .style import AIStyle, AIRelationship, AIDimension, AIStyleDimension, AIDimensionRelationshipMapping

# Score models
from .character_dimension import AICharacterDimension

# Log models
from .log import AIRequestLog

# Export all AI models
__all__ = [
    # Character and conversation
    "AICharacter",
    "AIMessageBuffer",
    "AIConversationItem",
    "AIConversationItemArchive",
    "AIConversationState",
    # Templates
    "AICharacterTemplate",
    "AIProfileTemplate",
    # Personality
    "AIPersonality",
    "AIPersonalityPlaceholder",
    # Style and relationship
    "AIStyle",
    "AIRelationship",
    "AIDimension",
    "AIStyleDimension",
    "AIDimensionRelationshipMapping",
    # Character Dimension
    "AICharacterDimension",
    # Log
    "AIRequestLog",
]

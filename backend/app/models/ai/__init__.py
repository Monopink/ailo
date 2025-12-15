"""
AI system models module.

This module imports all AI-related SQLAlchemy models.
"""

# Instance and conversation models
from .instance import (
    AIConversationItem,
    AIConversationItemArchive,
    AIConversationState,
    AIInstance,
    AIMessageBuffer,
)

# Score models
from .instance_dimension import AIInstanceDimension

# Log models
from .log import AIRequestLog

# Memory models
from .memory import AIInstanceMemory, AITemplateMemory

# Personality models
from .personality import AIPersonality, AIPersonalityPlaceholder

# Style and relationship models
from .style import (
    AIDimension,
    AIDimensionRelationshipMapping,
    AIRelationship,
    AIStyle,
    AIStyleDimension,
)

# Template models
from .template import AIPersona, AITemplate, AIType

# Export all AI models
__all__ = [
    "AIConversationItem",
    "AIConversationItemArchive",
    "AIConversationState",
    "AIDimension",
    "AIDimensionRelationshipMapping",
    "AIInstance",
    "AIInstanceDimension",
    "AIInstanceMemory",
    "AIMessageBuffer",
    "AIPersona",
    "AIPersonality",
    "AIPersonalityPlaceholder",
    "AIRelationship",
    "AIRequestLog",
    "AIStyle",
    "AIStyleDimension",
    "AITemplate",
    "AITemplateMemory",
    "AIType",
]

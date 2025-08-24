"""
AI system CRUD operations module.

This module imports all AI-related CRUD operations.
"""

# Character CRUD
from .character import CRUDAICharacter, ai_character

# Context CRUD
from .context import CRUDAIContext, ai_context

# Score CRUD
from .score import CRUDAIRelationshipScore, ai_relationship_score

# Log CRUD
from .log import CRUDAIRequestLog, ai_request_log

# Style CRUD
from .style import CRUDAIStyle, ai_style

# Personality CRUD
from .personality import CRUDAIPersonality, ai_personality

# Export all AI CRUD classes and instances
__all__ = [
    # Classes
    "CRUDAICharacter",
    "CRUDAIContext",
    "CRUDAIRelationshipScore",
    "CRUDAIRequestLog",
    "CRUDAIStyle",
    "CRUDAIPersonality",
    # Instances
    "ai_character",
    "ai_context",
    "ai_relationship_score",
    "ai_request_log",
    "ai_style",
    "ai_personality",
]

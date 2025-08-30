"""
Interface definitions for dependency inversion.

This module defines abstract interfaces that high-level modules depend on,
following the Dependency Inversion Principle.
"""

# AI Repository interfaces
from .ai_repository import (
    AICharacterRepository,
    AIPersonalityRepository,
    AIStyleRepository,
    AIRelationshipRepository,
    AITemplateRepository,
    AIContextRepository,
    AIRequestLogRepository,
)

__all__ = [
    # AI Repository interfaces
    "AICharacterRepository",
    "AIPersonalityRepository", 
    "AIStyleRepository",
    "AIRelationshipRepository",
    "AITemplateRepository",
    "AIContextRepository",
    "AIRequestLogRepository",
]

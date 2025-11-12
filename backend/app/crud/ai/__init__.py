"""
AI CRUD operations module.

This module provides unified data access for all AI-related operations,
supporting both standard CRUD operations and complex business queries.
"""

# AI Character CRUD
from .character import ai_character

# AI Personality CRUD
from .personality import ai_personality, ai_personality_placeholder

# AI Style CRUD
from .style import (
    ai_style,
    ai_relationship,
    ai_dimension_relationship_mapping,
    ai_style_dimension,
)


# AI Template CRUD
from .template import ai_character_template, ai_profile_template

# AI Request Log CRUD
from .request_log import ai_request_log

__all__ = [
    # Character management
    "ai_character",
    # Personality and style
    "ai_personality",
    "ai_personality_placeholder",
    "ai_style",
    "ai_relationship",
    "ai_dimension_relationship_mapping",
    "ai_style_dimension",
    # Template management
    "ai_character_template",
    "ai_profile_template",
    # Logging
    "ai_request_log",
]

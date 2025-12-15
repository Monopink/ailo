"""
AI CRUD operations module.

This module provides unified data access for all AI-related operations,
supporting both standard CRUD operations and complex business queries.
"""

# AI Instance CRUD
from .instance import ai_instance
from .memory import ai_instance_memory, ai_template_memory

# AI Personality CRUD
from .personality import ai_personality, ai_personality_placeholder

# AI Request Log CRUD
from .request_log import ai_request_log

# AI Style CRUD
from .style import ai_dimension_relationship_mapping, ai_relationship, ai_style, ai_style_dimension

# AI Template CRUD
from .template import ai_persona, ai_template

__all__ = [
    "ai_dimension_relationship_mapping",
    "ai_instance",
    "ai_instance_memory",
    "ai_persona",
    "ai_personality",
    "ai_personality_placeholder",
    "ai_relationship",
    "ai_request_log",
    "ai_style",
    "ai_style_dimension",
    "ai_template",
    "ai_template_memory",
]

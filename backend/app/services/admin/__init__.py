"""
Admin services module.

This module provides admin-related services for backend management.
"""

from .ai import (
    get_personality_templates,
    create_personality_template,
    get_personality_template,
    get_style_templates,
    create_style_template,
    get_style_template,
    get_relationship_types,
    create_relationship_type,
    get_ai_characters,
)
from .test import (
    create_virtual_user,
    get_virtual_users,
    delete_virtual_user,
    simulate_ai_chat,
    preview_system_prompt,
)

__all__ = [
    # AI template management
    "get_personality_templates",
    "create_personality_template",
    "get_personality_template",
    "get_style_templates",
    "create_style_template",
    "get_style_template",
    "get_relationship_types",
    "create_relationship_type",
    # AI character management
    "get_ai_characters",
    # AI testing
    "create_virtual_user",
    "get_virtual_users",
    "delete_virtual_user",
    "simulate_ai_chat",
    "preview_system_prompt",
]

"""
AI data access layer - focused database operations.

This module provides the data access layer for AI services with clear
separation of concerns across different query types.
"""

# Character-related query functions
from .character_queries import (
    get_character_with_relations,
    get_personality_with_placeholders,
    get_style_with_relationships,
    get_character_id_by_qiao_id,
    get_user_id_by_qiao_id,
    get_all_characters,
)

# Relationship scoring query functions
from .relationship_queries import (
    get_character_relationship_scores,
    get_relationship_score_ranges,
)

# Context and conversation query functions
from .context_queries import (
    get_conversation_contexts,
    get_conversation_history,
    get_conversation_item_by_id,
    get_items_for_archiving,
)

# Template-related query functions
from .template_queries import (
    get_profile_template_with_character_template,
    get_profile_template_by_id,
    get_character_template_by_id,
    check_template_reusability,
)

# Profile-related query functions
from .profile_queries import (
    get_user_profile,
    get_character_profile,
    get_profile_by_owner,
)

# Database updates (simple operations)
from .updates import (
    create_conversation_item,
    update_relationship_scores,
    mark_conversation_item_as_excluded,
    update_character_memory,
    update_character_status,
)

# Complex transactions
from .transactions import (
    create_character_with_relations,
)

__all__ = [
    # Character queries
    "get_character_with_relations",
    "get_personality_with_placeholders",
    "get_style_with_relationships",
    "get_character_id_by_qiao_id",
    "get_user_id_by_qiao_id",
    "get_all_characters",
    # Relationship queries
    "get_character_relationship_scores",
    "get_relationship_score_ranges",
    # Conversation queries
    "get_conversation_contexts",
    "get_conversation_history",
    "get_conversation_item_by_id",
    "get_items_for_archiving",
    # Template queries
    "get_profile_template_with_character_template",
    "get_profile_template_by_id",
    "get_character_template_by_id",
    "check_template_reusability",
    # Profile queries
    "get_user_profile",
    "get_character_profile",
    "get_profile_by_owner",
    # Updates
    "create_conversation_item",
    "update_relationship_scores",
    "mark_conversation_item_as_excluded",
    "update_character_memory",
    "update_character_status",
    # Transactions
    "create_character_with_relations",
]

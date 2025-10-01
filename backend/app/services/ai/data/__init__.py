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
    get_context_by_id,
    get_contexts_for_archiving,
    get_recent_contexts_count,
)

# Template-related query functions
from .template_queries import (
    get_profile_template_with_info,
    get_profile_template_by_id,
    get_info_template_by_id,
    check_template_reusability,
)

# Profile-related query functions
from .profile_queries import (
    get_user_profile,
    get_character_profile,
    get_profile_by_owner,
)

# Database mutations
from .mutations import (
    save_context_entry,
    update_context_status,
    update_relationship_scores,
    save_ai_response,
    mark_context_as_attack,
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
    "get_context_by_id",
    "get_contexts_for_archiving",
    "get_recent_contexts_count",
    # Template queries
    "get_profile_template_with_info",
    "get_profile_template_by_id",
    "get_info_template_by_id",
    "check_template_reusability",
    # Profile queries
    "get_user_profile",
    "get_character_profile",
    "get_profile_by_owner",
    # Mutations
    "save_context_entry",
    "update_context_status",
    "update_relationship_scores",
    "save_ai_response",
    "mark_context_as_attack",
    "update_character_memory",
    "update_character_status",
    # Transactions
    "create_character_with_relations",
]

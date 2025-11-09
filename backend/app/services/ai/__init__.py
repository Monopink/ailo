"""
AI services module - new simplified architecture.

This module provides the main entry points for AI-related functionality
using the new simplified 7-file architecture that replaces the complex
Repository/CRUD abstraction layers.

Main entry points:
- process_conversation: Handle complete AI conversation flow
- create_character_from_template: Create new AI character from template
"""

# Main conversation functions
from .conversation_flow import (
    process_conversation,
)

# Character creation functions
from .character_creation import (
    create_character_from_template,
)

# Character management
from .character_retrieval import (
    get_character_info,
    validate_character_status,
    get_character_configuration,
)

# Relationship management
from .relationship_scoring import (
    get_relationship_scores,
    initialize_relationship_scores,
    determine_relationship_type,
    update_character_relationship_scores,
)

# Prompt building
from .conversation_prompt import (
    build_system_prompt,
    replace_placeholders,
    get_response_schema,
)

# Memory management
from .conversation_memory import (
    process_memory_operations,
    archive_old_contexts,
)

# Contact request handling
from .contact_handler import (
    handle_ai_contact_request,
    ContactRequestDecision,
)

# LLM integration (moved to services.llm)
from services.llm import (
    chat_completion,
    get_primary_llm_config,
    chat_completion_with_provider,
)

# Data access functions (for advanced usage)
from .data import (
    get_character_with_relations,
    get_conversation_history,
    get_character_relationship_scores,
    save_context_entry,
    update_relationship_scores,
    save_ai_response,
)

__all__ = [
    # Main entry points
    "process_conversation",
    "create_character_from_template",
    # Character management
    "get_character_info",
    "validate_character_status",
    "get_character_configuration",
    # Relationship management
    "get_relationship_scores",
    "initialize_relationship_scores",
    "determine_relationship_type",
    "update_character_relationship_scores",
    # Prompt building
    "build_system_prompt",
    "replace_placeholders",
    "get_response_schema",
    # Memory management
    "process_memory_operations",
    "archive_old_contexts",
    # Contact request handling
    "handle_ai_contact_request",
    "ContactRequestDecision",
    # LLM integration
    "chat_completion",
    "get_primary_llm_config",
    "chat_completion_with_provider",
    # Data access (advanced)
    "get_character_with_relations",
    "get_conversation_history",
    "get_character_relationship_scores",
    "save_context_entry",
    "update_relationship_scores",
    "save_ai_response",
    # Note: Exception classes moved to exceptions/business.py for consistency
    # Import from exceptions module: AICharacterNotFoundError, AICharacterInactiveError,
    # AICharacterCreationError, AIConversationError, AIRelationshipError, AIServiceError
]

"""
AI memory management and state update module.

This module handles AI memory operations (add, replace, delete),
context status updates, and context archiving.
"""

from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from .queries import get_character_context, get_items_for_archiving
from .queries.updates import update_character_memory
from .queries.transactions import archive_contexts_transaction
from services.config import config_service

# AIServiceError import removed - memory operations now use tolerant error handling
from utils.logging import get_logger

logger = get_logger(__name__)


# Exception classes moved to exceptions/business.py for consistency


async def process_memory_operations(
    db: AsyncSession, character_qiao_id: str, operations: List[Dict[str, Any]]
) -> bool:
    """
    Process memory operations for AI character.

    Operations are executed in sequence on the character's memory.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
        operations: List of memory operation dictionaries

    Returns:
        True if successful, False otherwise
    """
    try:
        if not operations:
            logger.debug("no_memory_operations_to_process", character_qiao_id=character_qiao_id)
            return True

        # Get character context
        context = await get_character_context(db, character_qiao_id=character_qiao_id)

        if not context:
            logger.error("character_not_found_for_memory", character_qiao_id=character_qiao_id)
            return False

        current_memory = context.get("memory") or ""

        # Process operations in sequence
        for i, operation in enumerate(operations):
            try:
                current_memory = _apply_memory_operation(current_memory, operation)
                logger.debug(
                    "memory_operation_applied",
                    character_qiao_id=character_qiao_id,
                    operation_index=i,
                    operation_type=operation.get("operation"),
                    memory_length=len(current_memory),
                )
            except Exception as e:
                logger.error(
                    "memory_operation_failed",
                    error=str(e),
                    character_qiao_id=character_qiao_id,
                    operation_index=i,
                    operation=operation,
                )
                # Continue with other operations
                continue

        # Update character memory
        success = await update_character_memory(db, character_qiao_id, current_memory)
        if not success:
            logger.error("character_memory_update_failed", character_qiao_id=character_qiao_id)
            return False

        logger.info(
            "memory_operations_completed",
            character_qiao_id=character_qiao_id,
            operations_count=len(operations),
            final_memory_length=len(current_memory),
        )

        return True

    except Exception as e:
        logger.error(
            "memory_operations_processing_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
            operations=operations,
        )
        return False


# Context status updates are handled by the data.mutations layer


async def archive_old_contexts(db: AsyncSession, user_qiao_id: str, character_qiao_id: str) -> int:
    """
    Archive old conversation items to ai_conversation_items_archive table.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        character_qiao_id: Character's qiao_id

    Returns:
        Number of contexts archived
    """
    try:
        # Keep archive retention readable (config stored in days) but convert to seconds for queries.
        archive_time_days = await config_service.get_int(db, "ai_conversation_archive_time_days")
        archive_time_seconds = archive_time_days * 86400
        archive_max_count = await config_service.get_int(db, "ai_conversation_archive_max_count")
        archive_min_count = await config_service.get_int(db, "ai_conversation_archive_min_count")
        archive_threshold = await config_service.get_int(db, "ai_conversation_archive_threshold")

        items_to_archive, total_count = await get_items_for_archiving(
            db,
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
            max_age_seconds=int(archive_time_seconds),
            max_count=int(archive_max_count),
            archive_threshold=int(archive_threshold),
        )

        if total_count <= archive_min_count:
            logger.debug(
                "no_contexts_to_archive",
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
                reason="below_min_count",
            )
            return 0

        if not items_to_archive:
            logger.debug(
                "no_contexts_to_archive",
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
                reason="no_candidates",
            )
            return 0

        archived_count = await archive_contexts_transaction(
            db, contexts_to_archive=items_to_archive, character_qiao_id=character_qiao_id
        )

        logger.info(
            "contexts_archived",
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
            archived_count=archived_count,
            total_contexts=len(items_to_archive),
        )

        return archived_count

    except Exception as e:
        logger.error(
            "context_archiving_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
        )
        return 0


def _apply_memory_operation(memory: str, operation: Dict[str, Any]) -> str:
    """
    Apply a single memory operation to memory string.

    Args:
        memory: Current memory string
        operation: Memory operation dictionary

    Returns:
        Updated memory string

    Raises:
        MemoryOperationError: If operation is invalid
    """
    try:
        op_type = operation.get("operation")

        if op_type == "add":
            return _apply_add_operation(memory, operation)
        elif op_type == "replace":
            return _apply_replace_operation(memory, operation)
        elif op_type == "delete":
            return _apply_delete_operation(memory, operation)
        else:
            logger.warning("unknown_memory_operation_type", op_type=op_type, operation=operation)
            return memory  # Return unchanged memory for unknown operation types

    except Exception as e:
        logger.error("memory_operation_application_failed", error=str(e), operation=operation)
        return memory  # Return unchanged memory if operation fails


def _apply_add_operation(memory: str, operation: Dict[str, Any]) -> str:
    """Apply add operation to memory."""
    content = operation.get("content", "")
    if not content:
        logger.warning("add_operation_missing_content", operation=operation)
        return memory  # Return unchanged memory if no content to add

    insert_position = operation.get("insert_position", "end")

    if insert_position == "start":
        return content + "\n" + memory if memory else content
    elif insert_position == "end":
        return memory + "\n" + content if memory else content
    elif insert_position.startswith("after:"):
        target = insert_position[6:]  # Remove "after:" prefix
        if target in memory:
            return memory.replace(target, target + "\n" + content, 1)
        else:
            # Target not found, append to end
            return memory + "\n" + content if memory else content
    elif insert_position.startswith("before:"):
        target = insert_position[7:]  # Remove "before:" prefix
        if target in memory:
            return memory.replace(target, content + "\n" + target, 1)
        else:
            # Target not found, prepend to start
            return content + "\n" + memory if memory else content
    else:
        # Default to end
        return memory + "\n" + content if memory else content


def _apply_replace_operation(memory: str, operation: Dict[str, Any]) -> str:
    """Apply replace operation to memory."""
    target_text = operation.get("target_text", "")
    content = operation.get("content", "")

    if not target_text:
        logger.warning("replace_operation_missing_target_text", operation=operation)
        return memory  # Return unchanged memory if no target text specified

    if target_text in memory:
        return memory.replace(target_text, content, 1)  # Replace only first occurrence
    else:
        logger.warning("replace_target_not_found", target_text=target_text, memory_length=len(memory))
        return memory  # Return unchanged if target not found - memory operations can be tolerant


def _apply_delete_operation(memory: str, operation: Dict[str, Any]) -> str:
    """Apply delete operation to memory."""
    target_text = operation.get("target_text", "")

    if not target_text:
        logger.warning("delete_operation_missing_target_text", operation=operation)
        return memory  # Return unchanged memory if no target text specified

    if target_text in memory:
        # Remove target text and clean up extra newlines
        result = memory.replace(target_text, "", 1)
        # Clean up double newlines
        result = result.replace("\n\n\n", "\n\n")
        return result.strip()
    else:
        logger.warning("delete_target_not_found", target_text=target_text, memory_length=len(memory))
        return memory  # Return unchanged if target not found - memory operations can be tolerant

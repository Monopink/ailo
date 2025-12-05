"""
AI memory management and state update module.

This module handles AI memory operations (add, replace, delete),
context status updates, and context archiving.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.type_aliases import JSONDict
from app.services.config import config_service

# AIServiceError import removed - memory operations now use tolerant error handling
from app.utils.logging import get_logger

from .queries import get_instance_context, get_items_for_archiving
from .queries.transactions import archive_contexts_transaction
from .queries.updates import update_instance_memory

logger = get_logger(__name__)


# Exception classes moved to exceptions/business.py for consistency


async def process_memory_operations(
    db: AsyncSession, instance_qiao_id: str, operations: list[JSONDict]
) -> bool:
    """
    Process memory operations for AI instance.

    Operations are executed in sequence on the instance's memory.

    Args:
        db: Database session
        instance_qiao_id: Instance's qiao_id
        operations: List of memory operation dictionaries

    Returns:
        True if successful, False otherwise
    """
    if not operations:
        logger.debug("no_memory_operations_to_process", instance_qiao_id=instance_qiao_id)
        return True

    operation_success = False
    try:
        # Get instance context
        context = await get_instance_context(db, instance_qiao_id=instance_qiao_id)

        if not context:
            logger.error("instance_not_found_for_memory", instance_qiao_id=instance_qiao_id)
            return False

        current_memory = context.get("memory") or ""

        # Process operations in sequence
        for i, operation in enumerate(operations):
            try:
                current_memory = _apply_memory_operation(current_memory, operation)
                logger.debug(
                    "memory_operation_applied",
                    instance_qiao_id=instance_qiao_id,
                    operation_index=i,
                    operation_type=operation.get("operation"),
                    memory_length=len(current_memory),
                )
            except Exception as e:
                logger.error(
                    "memory_operation_failed",
                    error=str(e),
                    instance_qiao_id=instance_qiao_id,
                    operation_index=i,
                    operation=operation,
                )
                # Continue with other operations
                continue

        # Update instance memory
        success = await update_instance_memory(db, instance_qiao_id, current_memory)
        if not success:
            logger.error("instance_memory_update_failed", instance_qiao_id=instance_qiao_id)
            return False

        logger.info(
            "memory_operations_completed",
            instance_qiao_id=instance_qiao_id,
            operations_count=len(operations),
            final_memory_length=len(current_memory),
        )
        operation_success = True

    except Exception as e:
        logger.error(
            "memory_operations_processing_failed",
            error=str(e),
            instance_qiao_id=instance_qiao_id,
            operations=operations,
        )
        operation_success = False

    return operation_success


# Context status updates are handled by the data.mutations layer


async def archive_old_contexts(db: AsyncSession, user_qiao_id: str, instance_qiao_id: str) -> int:
    """
    Archive old conversation items to ai_conversation_items_archive table.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        instance_qiao_id: Instance's qiao_id

    Returns:
        Number of contexts archived
    """
    archived_count = 0
    try:
        # Keep archive retention readable (config stored in days)
        # but convert to seconds for queries.
        archive_time_days = await config_service.get_int(db, "ai_conversation_archive_time_days")
        archive_time_seconds = archive_time_days * 86400
        archive_max_count = await config_service.get_int(db, "ai_conversation_archive_max_count")
        archive_min_count = await config_service.get_int(db, "ai_conversation_archive_min_count")
        archive_threshold = await config_service.get_int(db, "ai_conversation_archive_threshold")

        items_to_archive, total_count = await get_items_for_archiving(
            db,
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
            max_age_seconds=int(archive_time_seconds),
            max_count=int(archive_max_count),
            archive_threshold=int(archive_threshold),
        )

        if total_count <= archive_min_count:
            logger.debug(
                "no_contexts_to_archive",
                instance_qiao_id=instance_qiao_id,
                user_qiao_id=user_qiao_id,
                reason="below_min_count",
            )
        elif not items_to_archive:
            logger.debug(
                "no_contexts_to_archive",
                instance_qiao_id=instance_qiao_id,
                user_qiao_id=user_qiao_id,
                reason="no_candidates",
            )
        else:
            archived_count = await archive_contexts_transaction(
                db, contexts_to_archive=items_to_archive, instance_qiao_id=instance_qiao_id
            )

            logger.info(
                "contexts_archived",
                instance_qiao_id=instance_qiao_id,
                user_qiao_id=user_qiao_id,
                archived_count=archived_count,
                total_contexts=len(items_to_archive),
            )

    except Exception as e:
        logger.error(
            "context_archiving_failed",
            error=str(e),
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
        )
        archived_count = 0

    return archived_count


def _apply_memory_operation(memory: str, operation: JSONDict) -> str:
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
    result_memory = memory
    try:
        op_type = _get_str(operation, "operation")

        if op_type == "add":
            result_memory = _apply_add_operation(memory, operation)
        elif op_type == "replace":
            result_memory = _apply_replace_operation(memory, operation)
        elif op_type == "delete":
            result_memory = _apply_delete_operation(memory, operation)
        else:
            logger.warning("unknown_memory_operation_type", op_type=op_type, operation=operation)
            result_memory = memory  # Return unchanged memory for unknown operation types

    except Exception as e:
        logger.error("memory_operation_application_failed", error=str(e), operation=operation)
        result_memory = memory  # Return unchanged memory if operation fails

    return result_memory


def _apply_add_operation(memory: str, operation: JSONDict) -> str:
    """Apply add operation to memory."""
    content = _get_str(operation, "content")
    if not content:
        logger.warning("add_operation_missing_content", operation=operation)
        return memory  # Return unchanged memory if no content to add

    insert_position = _get_str(operation, "insert_position") or "end"

    def _append(target_memory: str, payload: str) -> str:
        return f"{target_memory}\n{payload}" if target_memory else payload

    def _prepend(target_memory: str, payload: str) -> str:
        return f"{payload}\n{target_memory}" if target_memory else payload

    updated_memory = memory
    if insert_position == "start":
        updated_memory = _prepend(memory, content)
    elif insert_position == "end":
        updated_memory = _append(memory, content)
    elif insert_position.startswith("after:"):
        target = insert_position[6:]
        updated_memory = (
            memory.replace(target, f"{target}\n{content}", 1)
            if target in memory
            else _append(memory, content)
        )
    elif insert_position.startswith("before:"):
        target = insert_position[7:]
        updated_memory = (
            memory.replace(target, f"{content}\n{target}", 1)
            if target in memory
            else _prepend(memory, content)
        )
    else:
        updated_memory = _append(memory, content)

    return updated_memory


def _apply_replace_operation(memory: str, operation: JSONDict) -> str:
    """Apply replace operation to memory."""
    target_text = _get_str(operation, "target_text")
    content = _get_str(operation, "content") or ""

    if not target_text:
        logger.warning("replace_operation_missing_target_text", operation=operation)
        return memory  # Return unchanged memory if no target text specified

    if target_text in memory:
        return memory.replace(target_text, content, 1)  # Replace only first occurrence
    logger.warning("replace_target_not_found", target_text=target_text, memory_length=len(memory))
    return memory  # Return unchanged if target not found - memory operations can be tolerant


def _apply_delete_operation(memory: str, operation: JSONDict) -> str:
    """Apply delete operation to memory."""
    target_text = _get_str(operation, "target_text")

    if not target_text:
        logger.warning("delete_operation_missing_target_text", operation=operation)
        return memory  # Return unchanged memory if no target text specified

    if target_text in memory:
        # Remove target text and clean up extra newlines
        result = memory.replace(target_text, "", 1)
        # Clean up double newlines
        result = result.replace("\n\n\n", "\n\n")
        return result.strip()
    logger.warning("delete_target_not_found", target_text=target_text, memory_length=len(memory))
    return memory  # Return unchanged if target not found - memory operations can be tolerant


def _get_str(operation: JSONDict, key: str) -> str | None:
    """Extract string values from JSON memory operations."""
    value = operation.get(key)
    if isinstance(value, str):
        return value
    return None

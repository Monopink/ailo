"""
AI conversation service - conversation flow management.

This module handles the complete conversation processing flow,
coordinating all AI service components with clear error handling.
"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from .data import get_character_with_relations
from .relationship import (
    determine_relationship_type,
    calculate_new_scores,
    update_relationship_positions,
)
from .prompt import build_system_prompt, get_response_schema, build_conversation_context
from .context_manager import default_context_manager
from .memory import process_memory_operations, archive_old_contexts
from .data import (
    get_conversation_history,
    save_context_entry,
    update_context_status,
    mark_context_as_attack,
    update_character_status,
)
from .utils.validator import chat_completion_with_validation
from exceptions import AICharacterNotFoundError, AICharacterInactiveError, AIConversationError
from utils.logging import get_logger

logger = get_logger(__name__)


# Exception classes moved to exceptions/business.py for consistency


async def process_conversation(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    message_content: str,
    message_type: str = "text",
) -> Dict[str, Any]:
    """
    Process AI conversation following the complete 11-step flow.

    This is the main entry point that orchestrates the complete conversation
    processing flow as defined in the prototype design.

    Steps:
    1. Merge short-time messages (buffer) - simplified for now
    2. Store in ai_contexts table
    3. Find corresponding ai_character
    4. Find corresponding relationship_score
    5. Find relationship based on ai_style
    6. Apply relationship prompt and placeholders to personality template
    7. Get context and merge with system prompt
    8. Request LLM
    9. Validate with JSON Schema (done in LLM call)
    10. Update ai_relationship_score and other related content
    11. Reply message

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        character_qiao_id: Character's qiao_id
        message_content: User's message content
        message_type: Message type (text, image, etc.)

    Returns:
        Dictionary containing conversation processing result

    Raises:
        ConversationProcessingError: If processing fails
    """
    try:
        logger.info(
            "conversation_processing_started",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            message_type=message_type,
        )

        # Step 1: Message buffering (simplified - no actual buffering for now)
        buffered_message = {
            "content": message_content,
            "source_type": "original",
            "message_count": 1,
            "timestamp": None,  # Will be set by save_context_entry
        }

        # Step 2: Store in ai_contexts table
        context_data = {
            "character_qiao_id": character_qiao_id,
            "user_qiao_id": user_qiao_id,
            "role": 1,  # user role
            "content": buffered_message["content"],
            "source_type": 1,  # original
            "reply_status": 1,  # pending
        }

        # Save context entry - returns int (Snowflake ID) for internal use
        context_id = await save_context_entry(db, context_data)
        if not context_id:
            raise AIConversationError(
                conversation_step="save_context",
                reason="context_save_failed",
                message="Failed to save conversation context",
            )

        # Step 3: Find corresponding ai_character with relations
        character_info = await get_character_with_relations(db, character_qiao_id)
        if not character_info:
            raise AIConversationError(
                conversation_step="character_lookup",
                reason="character_not_found",
                message=f"Character not found: {character_qiao_id}",
            )

        # Step 4: Get relationship scores
        from .relationship import get_relationship_scores

        relationship_scores = await get_relationship_scores(db, character_qiao_id)

        # Step 5: Determine relationship type
        relationship_type = await determine_relationship_type(db, character_info, relationship_scores)

        # Step 6: Apply relationship prompt and placeholders to personality template
        system_prompt = await build_system_prompt(db, character_info, relationship_type, user_qiao_id)

        # Step 7: Get conversation context and prepare messages
        conversation_history = await build_conversation_context(
            db, character_qiao_id, user_qiao_id, max_context_length=10
        )

        # Prepare messages for LLM
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": message_content})

        # Get JSON schema for response validation
        json_schema = await get_response_schema(db, character_qiao_id)

        # Step 8: Request LLM with validation
        llm_result = await chat_completion_with_validation(
            db=db,
            messages=messages,
            json_schema=json_schema,
            enable_thinking=True,
        )

        if not llm_result["success"]:
            raise AIConversationError(
                conversation_step="llm_request",
                reason="llm_request_failed",
                message=f"LLM request failed: {llm_result['error']}",
            )

        # Step 9: JSON Schema validation (already done in LLM call)
        ai_response = llm_result["response"]

        # Step 10: Update ai_relationship_score and other related content
        await process_ai_response_updates(
            db, user_qiao_id, character_qiao_id, character_info, ai_response, context_id
        )

        # Step 11: Reply message
        await send_response_messages(db, user_qiao_id, character_qiao_id, ai_response)

        # Archive old contexts if needed
        await archive_old_contexts(db, character_qiao_id)

        logger.info(
            "conversation_processing_completed",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            context_id=context_id,
        )

        return {
            "success": True,
            "context_id": context_id,
            "response": ai_response,
            "usage": llm_result.get("usage", {}),
            "model": llm_result.get("model"),
            "config_used": llm_result.get("config_used"),
        }

    except (AICharacterNotFoundError, AICharacterInactiveError) as e:
        logger.error(
            "conversation_processing_character_error",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
        )
        raise AIConversationError(
            conversation_step="character_validation",
            reason="character_error",
            message=f"Character error: {str(e)}",
        )

    except Exception as e:
        logger.error(
            "conversation_processing_unexpected_error",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
        )
        raise AIConversationError(
            conversation_step="processing",
            reason="unexpected_error",
            message=f"Unexpected error in conversation processing: {str(e)}",
        )


async def build_full_context(
    db: AsyncSession, user_qiao_id: str, character_qiao_id: str, system_prompt: str
) -> Dict[str, Any]:
    """
    Build full conversation context including history and JSON schema.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        character_qiao_id: Character's qiao_id
        system_prompt: System prompt string

    Returns:
        Dictionary containing messages and JSON schema
    """
    try:
        # Get conversation history
        history = await get_conversation_history(db, user_qiao_id, character_qiao_id, limit=20)

        # Build messages array
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        for context in history:
            if context["role"] == 1:  # user
                messages.append({"role": "user", "content": context["content"]})
            elif context["role"] == 2:  # ai
                messages.append({"role": "assistant", "content": context["content"]})

        # Get JSON schema - need character info for this
        # For now, use None and let the LLM service handle it
        json_schema = None

        logger.debug(
            "full_context_built",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            messages_count=len(messages),
            history_count=len(history),
        )

        return {
            "messages": messages,
            "json_schema": json_schema,
            "history_count": len(history),
        }

    except Exception as e:
        logger.error(
            "full_context_build_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
        )
        raise AIConversationError(
            conversation_step="context_building",
            reason="context_build_failed",
            message=f"Failed to build full context: {str(e)}",
        )


async def process_ai_response_updates(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    character_info: Dict[str, Any],
    ai_response: Dict[str, Any],
    context_id: int,  # Note: int type for internal Snowflake ID
) -> None:
    """
    Process AI response and update related data.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        character_qiao_id: Character's qiao_id
        character_info: Character information
        ai_response: AI response dictionary
        context_id: Context ID (int - internal Snowflake ID)
    """
    try:
        # Update context status to processing - using int ID internally
        await update_context_status(db, context_id, 2)  # processing

        # Handle attack detection
        if ai_response.get("attack_detected", False):
            await handle_attack_detection(db, user_qiao_id, character_qiao_id, context_id)

        # Update relationship scores
        if ai_response.get("score"):
            # Calculate new scores using the new system
            new_scores = await calculate_new_scores(db, character_info, ai_response["score"])

            # Update relationship positions
            character_id = character_info["character_id"]
            if character_id and new_scores:
                await update_relationship_positions(db, character_id, new_scores)

        # Process memory operations
        if ai_response.get("should_update_memory", False) and ai_response.get("memory_operations"):
            await process_memory_operations(db, character_qiao_id, ai_response["memory_operations"])

        # Handle blocking
        if ai_response.get("should_block", False):
            await handle_character_blocking(db, character_qiao_id)

        # Update context status to done - using int ID internally
        await update_context_status(db, context_id, 3)  # done

        logger.debug(
            "ai_response_updates_completed",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            context_id=context_id,
        )

    except Exception as e:
        logger.error(
            "ai_response_updates_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            context_id=context_id,
        )
        # Non-fatal error: log but continue


async def send_response_messages(
    db: AsyncSession, user_qiao_id: str, character_qiao_id: str, ai_response: Dict[str, Any]
) -> None:
    """
    Send response messages to user.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        character_qiao_id: Character's qiao_id
        ai_response: AI response dictionary
    """
    try:
        if not ai_response.get("should_reply", False):
            logger.debug("ai_chose_not_to_reply", character_qiao_id=character_qiao_id)
            return

        # Send outgoing messages
        outgoing_messages = ai_response.get("outgoing_messages", [])
        for message in outgoing_messages:
            await send_single_message(db, character_qiao_id, user_qiao_id, message)

        # TODO: Implement followup messages with delay
        followup_messages = ai_response.get("followup_messages", [])
        if followup_messages:
            logger.debug(
                "followup_messages_scheduled",
                character_qiao_id=character_qiao_id,
                count=len(followup_messages),
            )
            # For now, just log that followup messages would be scheduled

        logger.info(
            "response_messages_sent",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            outgoing_count=len(outgoing_messages),
            followup_count=len(followup_messages),
        )

    except Exception as e:
        logger.error(
            "response_messages_send_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
        )
        # Non-fatal error: log but don't raise


async def send_single_message(db: AsyncSession, from_qiao_id: str, to_qiao_id: str, content: str) -> None:
    """
    Send a single message.

    Args:
        db: Database session
        from_qiao_id: Sender's qiao_id
        to_qiao_id: Recipient's qiao_id
        content: Message content
    """
    try:
        # TODO: Integrate with message service to actually send message
        # For now, just log the message that would be sent

        logger.info(
            "message_would_be_sent",
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            content=content[:100] + "..." if len(content) > 100 else content,
        )

    except Exception as e:
        logger.error(
            "single_message_send_failed", error=str(e), from_qiao_id=from_qiao_id, to_qiao_id=to_qiao_id
        )


async def handle_attack_detection(
    db: AsyncSession, user_qiao_id: str, character_qiao_id: str, context_id: int
) -> None:
    """
    Handle detected prompt injection attack.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        character_qiao_id: Character's qiao_id
        context_id: Context ID (int - internal Snowflake ID)
    """
    try:
        # Mark context as attack using data layer - using int ID internally
        success = await mark_context_as_attack(db, context_id)

        if success:
            # TODO: Log security incident to user_security_logs
            logger.warning(
                "attack_detected_and_handled",
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                context_id=context_id,
            )
        else:
            logger.error(
                "failed_to_mark_attack",
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                context_id=context_id,
            )

    except Exception as e:
        logger.error(
            "attack_handling_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            context_id=context_id,
        )


async def handle_character_blocking(db: AsyncSession, character_qiao_id: str) -> None:
    """
    Handle character blocking (delete friend).

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
    """
    try:
        # Block character using data layer
        success = await update_character_status(db, character_qiao_id, 3)  # blocked

        if success:
            logger.warning("character_blocked", character_qiao_id=character_qiao_id)
        else:
            logger.error("failed_to_block_character", character_qiao_id=character_qiao_id)

    except Exception as e:
        logger.error("character_blocking_failed", error=str(e), character_qiao_id=character_qiao_id)

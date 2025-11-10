"""
AI conversation service - conversation flow management.

This module handles the complete conversation processing flow,
coordinating all AI service components with clear error handling.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from enums.common import AIContextRole
from .queries import get_character_with_relations
from .relationship_scoring import (
    get_relationship_scores,
    determine_relationship_type,
    calculate_new_scores,
    update_relationship_positions,
    update_current_relationship,
)
from .conversation_prompt import build_system_prompt, get_response_schema, build_conversation_context
from .conversation_memory import process_memory_operations, archive_old_contexts
from .queries import (
    get_conversation_history,
    save_context_entry,
    mark_context_as_attack,
    update_character_status,
)
from .queries.updates import is_context_locked
from .utils.validator import chat_completion_with_validation
from services.llm.client import select_config_for_ai, validate_ai_response
from exceptions import AICharacterNotFoundError, AICharacterInactiveError, AIConversationError
from utils.logging import get_logger
from crud.contact import contact as contact_crud
from enums.templates import CHAT_INFO_TEMPLATES, ChatInfoType
from services.message.outbound.helpers import send_chat_info
from services.message.outbound.sender import send_message
from enums import MessageType

logger = get_logger(__name__)


# Exception classes moved to exceptions/business.py for consistency


async def process_conversation(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    message_content: str,
    message_type: str = "text",
    config_name: Optional[str] = None,
    request_overrides: Optional[Dict[str, Any]] = None,
    locked_context_id: Optional[int] = None,
    persist: bool = True,
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
    10. Update ai_character_dimension and other related content
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

        # Note: user context creation/aggregation is handled by message.buffer
        # This function assumes, when called by buffer, that locked_context_id points
        # to the currently LOCKED user window and message_content reflects its content.

        # Step 3: Find corresponding ai_character with relations
        character_info = await get_character_with_relations(db, character_qiao_id)
        if not character_info:
            raise AIConversationError(
                conversation_step="character_lookup",
                reason="character_not_found",
                message=f"Character not found: {character_qiao_id}",
            )

        # Step 3.5: Validate message permission (bidirectional relationship)
        # Get contact relationship and AI character for validation
        from models.contact import Contact
        from models.ai.character import AICharacter
        from services.message.security.validation import message_validation_service
        from sqlalchemy import select

        # Find contact by user and character qiao_ids
        contact_stmt = select(Contact).where(
            Contact.user_qiao_id == user_qiao_id,
            Contact.contact_qiao_id == character_qiao_id,
            Contact.contact_type == 2,  # AI character
        )
        contact_result = await db.execute(contact_stmt)
        contact = contact_result.scalar_one_or_none()

        if not contact:
            logger.warning(
                "contact_not_found_for_validation",
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
            )
            raise AIConversationError(
                conversation_step="permission_validation",
                reason="contact_not_found",
                message=f"Contact relationship not found between user and character",
            )

        # Get AI character instance for validation
        character_stmt = select(AICharacter).where(AICharacter.qiao_id == character_qiao_id)
        character_result = await db.execute(character_stmt)
        character = character_result.scalar_one_or_none()

        if not character:
            raise AIConversationError(
                conversation_step="permission_validation",
                reason="character_not_found",
                message=f"Character not found: {character_qiao_id}",
            )

        # Validate message permission
        validation_result = await message_validation_service.validate_message_permission(
            db=db, from_qiao_id=user_qiao_id, character=character, contact=contact
        )

        if not validation_result.allowed:
            logger.warning(
                "message_permission_denied",
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                reason=validation_result.reason,
                error_code=validation_result.error_code,
            )
            try:
                template_key = validation_result.chat_info_type or ChatInfoType.MESSAGE_BLOCKED
                content = CHAT_INFO_TEMPLATES.get(template_key)
                if content and contact.conv_id:
                    await send_chat_info(
                        db=db,
                        to_qiao_id=user_qiao_id,
                        conv_id=contact.conv_id,
                        content=content,
                    )
            except Exception as send_error:
                logger.error(
                    "chat_info_send_failed",
                    user_qiao_id=user_qiao_id,
                    character_qiao_id=character_qiao_id,
                    error=str(send_error),
                )
            raise AIConversationError(
                conversation_step="permission_validation",
                reason=validation_result.error_code or "permission_denied",
                message=validation_result.reason or "Message permission denied",
            )

        # Step 4: Get relationship scores
        relationship_scores = await get_relationship_scores(db, character_qiao_id)

        # Step 5: Determine relationship type
        relationship_type = await determine_relationship_type(db, character_info, relationship_scores)

        # Step 6: Apply relationship prompt and placeholders to personality template
        system_prompt = await build_system_prompt(db, character_info, relationship_type, user_qiao_id)

        # Step 7: Get conversation context and prepare messages
        conversation_history = await build_conversation_context(
            db, character_qiao_id, user_qiao_id, max_context_length=None
        )

        # Prepare messages for LLM
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": message_content})

        # Get JSON schema for response validation
        json_schema = await get_response_schema(db, character_qiao_id)

        # Pre-check: Validate config supports JSON Schema
        # This will raise ConfigNotVerifiedError or JSONSchemaNotSupportedError if config is not suitable
        config, provider = await select_config_for_ai(db, config_name)

        logger.info(
            "ai_conversation_config_validated",
            config_name=config.name,
            provider=provider.name,
            json_schema_mode=config.json_schema_mode,
        )

        # Extract character-specific request parameters
        character_request_params = character_info.get("character", {}).request_params or {}
        # Apply test-time overrides (e.g., mock provider)
        if request_overrides:
            try:
                character_request_params = {**(character_request_params or {}), **request_overrides}
            except Exception:
                # Ensure robustness even if types mismatch
                pass
        if character_request_params:
            logger.debug(
                "using_character_request_params",
                character_qiao_id=character_qiao_id,
                params=character_request_params,
            )

        # Step 8: Request LLM with validation
        # No hardcoded parameters - use config priority: character_request_params > config
        llm_result = await chat_completion_with_validation(
            db=db,
            messages=messages,
            json_schema=json_schema,
            name=config_name,
            character_request_params=character_request_params,
        )

        if not llm_result["success"]:
            raise AIConversationError(
                conversation_step="llm_request",
                reason="llm_request_failed",
                message=f"LLM request failed: {llm_result['error']}",
            )

        # Step 9: JSON Schema validation (already done in LLM call)
        ai_response = llm_result["response"]

        # Post-check: Validate response format
        # Convert Python dict to JSON string for validation
        raw_content = llm_result.get("raw_content")
        if not raw_content:
            # If no raw_content, convert Python object to JSON string
            import json

            raw_content = json.dumps(ai_response, ensure_ascii=False)
        await validate_ai_response(db, config, raw_content, allow_auto_update=False)

        # Step 10 & 11: Save all conversation results in single atomic transaction
        if persist:
            from .queries.transactions import save_conversation_result

            await save_conversation_result(
                db=db,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                character_info=character_info,
                ai_response=ai_response,
                new_scores=ai_response.get("score"),
                memory_operations=ai_response.get("memory_operations"),
                llm_result={
                    "success": True,
                    "model": llm_result.get("model"),
                    "usage": llm_result.get("usage", {}),
                    "config_used": llm_result.get("config_used"),
                    "request_payload": llm_result.get("request_payload"),
                    "response_time": llm_result.get("response_time", 0),
                },
                locked_context_id=locked_context_id,
            )
        else:
            # Non-persist mode: only update scores/memory without sending messages
            await process_ai_response_updates(
                db, user_qiao_id, character_qiao_id, character_info, ai_response, locked_context_id, persist=False
            )

        # Archive old contexts if needed (per user-character conversation)
        await archive_old_contexts(db, user_qiao_id, character_qiao_id)

        logger.info(
            "conversation_processing_completed",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            context_id=locked_context_id,
        )

        return {
            "success": True,
            "context_id": locked_context_id,
            "response": ai_response,
            "usage": llm_result.get("usage", {}),
            "model": llm_result.get("model"),
            "config_used": llm_result.get("config_used"),
            "request_payload": llm_result.get("request_payload"),
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
    context_id: Optional[int],  # Optional: only present when called by buffer
    *,
    persist: bool = True,
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
        # No state transition here; buffer controls OPEN -> LOCKED -> COMPLETE

        # Handle attack detection
        if persist and ai_response.get("attack_detected", False) and context_id is not None:
            await handle_attack_detection(db, user_qiao_id, character_qiao_id, context_id)

        # Update relationship scores
        if ai_response.get("score"):
            # Calculate new scores using the new system
            new_scores = await calculate_new_scores(db, character_info, ai_response["score"])

            # Update relationship positions
            character_id = character_info["character_id"]
            if persist and character_id and new_scores:
                await update_relationship_positions(db, character_id, new_scores)

                # Re-evaluate and persist current relationship after score update
                from .queries import get_character_relationship_scores

                latest_scores = await get_character_relationship_scores(db, character_id)
                if persist and latest_scores:
                    rel = await determine_relationship_type(db, character_info, latest_scores)
                    if rel and rel.get("relationship"):
                        relationship = rel["relationship"]
                        display_name = getattr(
                            relationship, "display_name", getattr(relationship, "name", "")
                        )
                        await update_current_relationship(db, character_id, relationship.id, display_name)

        # Process memory operations
        if persist and ai_response.get("should_update_memory", False) and ai_response.get("memory_operations"):
            await process_memory_operations(db, character_qiao_id, ai_response["memory_operations"])

        # Handle blocking
        if persist and ai_response.get("should_block", False):
            await handle_character_blocking(db, character_qiao_id)

        # Finalization to COMPLETE is handled by buffer after this function returns

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
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    ai_response: Dict[str, Any],
    locked_context_id: Optional[int] = None,
) -> None:
    """
    Send response messages to user and save to ai_contexts.

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

        # Before sending, if we are tied to a locked window, ensure it is still LOCKED
        if locked_context_id is not None:
            still_locked = await is_context_locked(db, locked_context_id)
            if not still_locked:
                logger.warning(
                    "result_discarded_due_to_preemption",
                    character_qiao_id=character_qiao_id,
                    user_qiao_id=user_qiao_id,
                    context_id=locked_context_id,
                )
                return

        # Send outgoing messages and save to ai_contexts (assistant rows use no state)
        outgoing_messages = ai_response.get("outgoing_messages", [])
        for message in outgoing_messages:
            # Send message (currently just logs)
            await send_single_message(db, character_qiao_id, user_qiao_id, message)

            # Save AI response to ai_contexts table
            context_data = {
                "character_qiao_id": character_qiao_id,
                "user_qiao_id": user_qiao_id,
                "role": AIContextRole.ASSISTANT,  # assistant
                "content": message,
            }
            context_id = await save_context_entry(db, context_data)

            if context_id:
                logger.debug(
                    "ai_response_saved_to_context",
                    character_qiao_id=character_qiao_id,
                    user_qiao_id=user_qiao_id,
                    context_id=context_id,
                )
            else:
                logger.error(
                    "failed_to_save_ai_response_to_context",
                    character_qiao_id=character_qiao_id,
                    user_qiao_id=user_qiao_id,
                )

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
            "response_messages_sent_and_saved",
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
        contact = await contact_crud.get_user_contact(
            db,
            user_qiao_id=to_qiao_id,
            contact_qiao_id=from_qiao_id,
        )

        if not contact:
            logger.error(
                "contact_not_found_for_sending",
                from_qiao_id=from_qiao_id,
                to_qiao_id=to_qiao_id,
            )
            return

        await send_message(
            db=db,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            conv_id=contact.conv_id,
            content=content,
            message_type=MessageType.TEXT,
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
            # TODO: Log security incident to user_violation_logs
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

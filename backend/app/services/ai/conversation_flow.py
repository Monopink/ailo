"""
AI conversation service - conversation flow management.

This module handles the complete conversation processing flow,
coordinating all AI service components with clear error handling.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai.queries.character_queries import get_character_context
from services.ai.queries.context_queries import get_conversation_history
from services.ai.queries.updates import update_character_status, mark_conversation_item_as_excluded
from services.ai.relationship_scoring import (
    get_relationship_scores,
    determine_relationship_type,
    calculate_new_scores,
    update_relationship_positions,
    update_current_relationship,
)
from services.ai.conversation_prompt import (
    build_system_prompt,
    build_response_schema,
    build_conversation_context,
)
from services.ai.conversation_memory import process_memory_operations, archive_old_contexts
from services.message.processing.buffer import is_buffer_cancelled
from services.ai.utils.validator import invoke_llm_with_validation
from services.llm.client import select_config_for_ai, validate_ai_response
from services.llm.types import LLMSessionContext
from services.llm.streaming_policy import extract_stream_override, resolve_streaming_decision
from exceptions import AICharacterNotFoundError, AICharacterInactiveError, AIConversationError
from services.ai.types import CharacterContext
from utils.logging import get_logger
from enums.templates import CHAT_INFO_TEMPLATES, ChatInfoType
from services.message.outbound.helpers import send_chat_info

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
    locked_buffer_id: Optional[int] = None,
    user_message_item_id: Optional[int] = None,
    message_blocks: Optional[List[Dict[str, Any]]] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """
    Process AI conversation following the complete 11-step flow.

    This is the main entry point that orchestrates the complete conversation
    processing flow as defined in the prototype design.

    Steps:
    1. Merge short-time messages (buffer) - simplified for now
    2. Persist user window into ai_conversation_items
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
        message_content: User's message content (text fallback)
        message_type: Message type (text, image, etc.)
        locked_buffer_id: Locked buffer ID (if triggered by buffer)
        user_message_item_id: Conversation history row id tied to locked buffer
        message_blocks: Structured content blocks (Responses API format)

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
        # This function assumes, when called by buffer, that locked_buffer_id points
        # to the currently LOCKED user window and message_content reflects its content.

        # Step 3: Find corresponding ai_character context
        context = await get_character_context(db, character_qiao_id=character_qiao_id)
        if not context:
            raise AIConversationError(
                conversation_step="character_lookup",
                reason="character_not_found",
                message=f"Character not found: {character_qiao_id}",
            )

        # Step 3.5: Validate message permission (bidirectional relationship)
        # Skip contact validation in test mode (persist=False)
        if persist:
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
                    message="Contact relationship not found between user and character",
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
        else:
            logger.debug(
                "skipping_contact_validation_in_test_mode",
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
            )

        # Step 4: Get relationship scores
        relationship_scores = await get_relationship_scores(db, character_qiao_id)

        # Step 5: Determine relationship type
        relationship_type = await determine_relationship_type(db, context, relationship_scores)

        # Step 6: Apply relationship prompt and placeholders to personality template
        system_prompt = await build_system_prompt(db, context, relationship_type, user_qiao_id)

        # Step 7: Get conversation context and prepare messages
        conversation_history = await build_conversation_context(
            db,
            character_qiao_id,
            user_qiao_id,
            max_context_length=None,
            character_timezone=context.get("timezone"),
        )

        # Prepare messages for LLM (business format)
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "message_type": "text",
                    "text_content": system_prompt,
                }
            )
        messages.extend(conversation_history)

        user_text = message_content
        if not user_text and message_blocks:
            user_text = _blocks_to_text(message_blocks)

        def _should_append_user_message() -> bool:
            """
            Determine if current user message should be appended to messages array.

            Compares the last message in conversation_history with the current message,
            stripping time prefixes to avoid false positives.
            """
            if not user_text:
                return False
            if not (persist and user_message_item_id is not None):
                return True
            if not conversation_history:
                return True
            last_entry = conversation_history[-1]
            if last_entry.get("role") != "user":
                return True
            last_text = last_entry.get("text_content")
            if last_text is None:
                return True

            # Strip normalized "[prefix] " wrapper to compare content only
            last_text_clean = last_text.strip()
            if last_text_clean.startswith("["):
                closing_index = last_text_clean.find("]")
                if closing_index != -1:
                    last_text_clean = last_text_clean[closing_index + 1 :].lstrip()
            return last_text_clean != user_text.strip()

        if _should_append_user_message():
            prefix = _format_now_prefix(context.get("timezone"))
            formatted_user_text = f"[{prefix}] {user_text}" if prefix else user_text
            messages.append(
                {
                    "role": "user",
                    "message_type": "text",
                    "text_content": formatted_user_text,
                }
            )

        # Get JSON schema for response validation
        json_schema = build_response_schema(context)

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
        character_request_params = dict(context.get("request_params") or {})
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

        stream_override = extract_stream_override(character_request_params)
        if stream_override is not None:
            character_request_params["enable_streaming"] = stream_override

        # Step 8: Request LLM with validation and streaming early stop
        # Create preemption checker if we have a locked context
        preemption_checker = None
        if locked_buffer_id is not None:
            preview_decision = resolve_streaming_decision(
                config=config,
                provider=provider,
                enable_override=stream_override,
                has_preemption_checker=True,
            )

            if preview_decision.should_stream:

                async def check_preemption() -> bool:
                    """Check if buffer has been cancelled during streaming."""
                    return await is_buffer_cancelled(db, locked_buffer_id)

                preemption_checker = check_preemption
            else:
                logger.debug(
                    "streaming_disabled_for_context",
                    buffer_id=locked_buffer_id,
                    reason=preview_decision.reason,
                )

        # No hardcoded parameters - use config priority: character_request_params > config
        llm_result = await invoke_llm_with_validation(
            db=db,
            messages=messages,
            json_schema=json_schema,
            name=config_name,
            character_request_params=character_request_params,
            preemption_checker=preemption_checker,
            session_context=LLMSessionContext(
                user_qiao_id=user_qiao_id, character_qiao_id=character_qiao_id
            ),
        )

        # Check if request was preempted
        if llm_result.get("preempted", False):
            logger.info(
                "conversation_preempted_during_llm",
                buffer_id=locked_buffer_id,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
            )
            return {
                "success": False,
                "error": "Conversation preempted by new message",
                "preempted": True,
                "buffer_id": locked_buffer_id,
            }

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
            raw_content = json.dumps(ai_response, ensure_ascii=False)
        await validate_ai_response(db, config, raw_content, allow_auto_update=False)

        # Step 10 & 11: Save all conversation results in single atomic transaction
        assistant_item_id: Optional[int] = None
        if persist:
            from core.database import SessionLocal
            from .queries.transactions import process_llm_response

            await process_llm_response(
                db=db,
                session_factory=SessionLocal,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                character_context=context,
                ai_response=ai_response,
                llm_result={
                    "success": True,
                    "model": llm_result.get("model"),
                    "usage": llm_result.get("usage", {}),
                    "config_used": llm_result.get("config_used"),
                    "request_payload": llm_result.get("request_payload"),
                    "response_time": llm_result.get("response_time", 0),
                    "response_id": llm_result.get("response_id"),
                    "cache_hit": llm_result.get("cache_hit"),
                    "cache_strategy": llm_result.get("cache_strategy"),
                    "raw_response": llm_result.get("raw_response"),
                    "raw_content": llm_result.get("raw_content"),
                    "tool_calls": llm_result.get("tool_calls"),
                    "reasoning_content": llm_result.get("reasoning_content"),
                    "finish_reason": llm_result.get("finish_reason"),
                    "streaming": llm_result.get("streaming"),
                },
                locked_buffer_id=locked_buffer_id,
                user_message_item_id=user_message_item_id,
            )
        else:
            # Non-persist mode: only update scores/memory without sending messages
            await process_ai_response_updates(
                db,
                user_qiao_id,
                character_qiao_id,
                context,
                ai_response,
                locked_buffer_id,
                user_message_item_id,
                persist=False,
            )

        # Archive old contexts if needed (per user-character conversation)
        await archive_old_contexts(db, user_qiao_id, character_qiao_id)

        logger.info(
            "conversation_processing_completed",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            buffer_id=locked_buffer_id,
        )

        return {
            "success": True,
            "buffer_id": locked_buffer_id,
            "assistant_item_id": assistant_item_id,
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


async def process_ai_response_updates(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    context: CharacterContext,
    ai_response: Dict[str, Any],
    buffer_id: Optional[int],  # Locked buffer id
    user_message_item_id: Optional[int],
    *,
    persist: bool = True,
) -> None:
    """
    Process AI response and update related data.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        character_qiao_id: Character's qiao_id
        context: Character context data
        ai_response: AI response dictionary
        buffer_id: Buffer ID (used for logging only)
        user_message_item_id: Conversation item identifier linked to buffer
    """
    try:
        # No state transition here; buffer controls OPEN -> LOCKED -> COMPLETE

        # Handle attack detection
        if persist and ai_response.get("attack_detected", False) and user_message_item_id is not None:
            await handle_attack_detection(db, user_qiao_id, character_qiao_id, user_message_item_id)

        # Update relationship scores
        if ai_response.get("score"):
            # Calculate new scores using the new system
            new_scores = await calculate_new_scores(db, context, ai_response["score"])

            # Update relationship positions
            character_id = context["character_id"]
            if persist and character_id and new_scores:
                await update_relationship_positions(db, character_id, new_scores)

                # Re-evaluate and persist current relationship after score update
                from .queries import get_character_relationship_scores

                latest_scores = await get_character_relationship_scores(db, character_id)
                if persist and latest_scores:
                    rel = await determine_relationship_type(db, context, latest_scores)
                    if rel and rel.get("relationship"):
                        relationship = rel["relationship"]
                        display_name = getattr(
                            relationship, "display_name", getattr(relationship, "name", "")
                        )
                        await update_current_relationship(db, character_id, relationship.id, display_name)

        # Process memory operations
        if (
            persist
            and ai_response.get("should_update_memory", False)
            and ai_response.get("memory_operations")
        ):
            await process_memory_operations(db, character_qiao_id, ai_response["memory_operations"])

        # Handle blocking
        if persist and ai_response.get("should_block", False):
            await handle_character_blocking(db, character_qiao_id)

        # Finalization to COMPLETE is handled by buffer after this function returns

        logger.debug(
            "ai_response_updates_completed",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            buffer_id=buffer_id,
        )

    except Exception as e:
        logger.error(
            "ai_response_updates_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            buffer_id=buffer_id,
        )
        # Non-fatal error: log but continue


async def handle_attack_detection(
    db: AsyncSession, user_qiao_id: str, character_qiao_id: str, conversation_item_id: int
) -> None:
    """
    Handle detected prompt injection attack.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        character_qiao_id: Character's qiao_id
        conversation_item_id: Conversation row tied to the suspicious message
    """
    try:
        # Mark conversation item as excluded from context using data layer
        success = await mark_conversation_item_as_excluded(db, conversation_item_id)

        if success:
            # TODO: Log security incident to user_violation_logs
            logger.warning(
                "attack_detected_and_handled",
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                conversation_item_id=conversation_item_id,
            )
        else:
            logger.error(
                "failed_to_mark_attack",
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                conversation_item_id=conversation_item_id,
            )

    except Exception as e:
        logger.error(
            "attack_handling_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            conversation_item_id=conversation_item_id,
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


def _blocks_to_text(blocks: List[Dict[str, Any]]) -> str:
    """Flatten provider-style blocks into a single text string."""

    fragments: List[str] = []
    for block in blocks:
        text_value = block.get("text")
        if text_value:
            fragments.append(text_value)
    return "\n".join(fragments)


def _format_now_prefix(timezone_name: Optional[str]) -> Optional[str]:
    """
    Format current time with humanized format.

    For current messages, always returns "今天HH:MM" format.
    Falls back to Asia/Shanghai timezone.
    """
    try:
        tz = timezone_name or "Asia/Shanghai"
        try:
            tzinfo = ZoneInfo(tz)
        except Exception:
            tzinfo = ZoneInfo("Asia/Shanghai")
        now = datetime.now(tzinfo)
        # For current messages, always use "今天HH:MM" format
        return f"今天{now.strftime('%H:%M')}"
    except Exception:
        return None

"""
AI conversation context management module.

This module handles conversation history management, message merging logic,
and context length control for AI conversations.
"""

from typing import Dict, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from enums.common import AIContextRole
from .data import get_conversation_contexts, save_context_entry
from exceptions import AIServiceError
from utils.logging import get_logger

logger = get_logger(__name__)


class ContextManager:
    """Manages AI conversation contexts with message merging and length control."""

    def __init__(self, max_context_length: int = 20, merge_window_seconds: int = 30):
        """
        Initialize context manager.

        Args:
            max_context_length: Maximum number of context entries to maintain
            merge_window_seconds: Time window for message merging in seconds
        """
        self.max_context_length = max_context_length
        self.merge_window_seconds = merge_window_seconds

    async def get_formatted_context(
        self,
        db: AsyncSession,
        character_qiao_id: str,
        user_qiao_id: str,
        include_system_messages: bool = True,
    ) -> List[Dict[str, str]]:
        """
        Get formatted conversation context for LLM.

        Args:
            db: Database session
            character_qiao_id: Character's qiao_id
            user_qiao_id: User's qiao_id
            include_system_messages: Whether to include system messages

        Returns:
            List of formatted message dictionaries

        Raises:
            AIServiceError: If context retrieval fails
        """
        try:
            # Get raw contexts from database
            contexts = await get_conversation_contexts(
                db, character_qiao_id, user_qiao_id, self.max_context_length
            )

            if not contexts:
                logger.debug(
                    "no_contexts_found_for_formatting",
                    character_qiao_id=character_qiao_id,
                    user_qiao_id=user_qiao_id,
                )
                return []

            # Filter and format contexts
            formatted_messages = []
            for context in contexts:
                role = self._map_role_to_message_role(context["role"])
                content = context["content"]

                # Skip system messages if not requested
                if not include_system_messages and role == "system":
                    continue

                # Skip empty content
                if not content or not content.strip():
                    continue

                formatted_messages.append({"role": role, "content": content.strip()})

            logger.debug(
                "context_formatted_for_llm",
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
                raw_contexts=len(contexts),
                formatted_messages=len(formatted_messages),
            )

            return formatted_messages

        except Exception as e:
            logger.error(
                "context_formatting_failed",
                error=str(e),
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
            )
            raise AIServiceError(
                ai_service="context_management",
                reason="formatting_failed",
                message=f"Failed to format conversation context: {str(e)}",
            )

    async def add_user_message(
        self,
        db: AsyncSession,
        character_qiao_id: str,
        user_qiao_id: str,
        message_content: str,
        merge_with_recent: bool = True,
    ) -> int:
        """
        Add user message to context with optional merging.

        Args:
            db: Database session
            character_qiao_id: Character's qiao_id
            user_qiao_id: User's qiao_id
            message_content: Message content
            merge_with_recent: Whether to merge with recent messages

        Returns:
            Context ID of the saved entry

        Raises:
            AIServiceError: If saving fails
        """
        try:
            # Check if we should merge with recent messages
            if merge_with_recent:
                merged_content = await self._merge_with_recent_messages(
                    db, character_qiao_id, user_qiao_id, message_content, role=1  # user role
                )
                if merged_content != message_content:
                    logger.debug(
                        "user_message_merged_with_recent",
                        character_qiao_id=character_qiao_id,
                        user_qiao_id=user_qiao_id,
                        original_length=len(message_content),
                        merged_length=len(merged_content),
                    )
                    message_content = merged_content

            # Save context entry
            context_data = {
                "character_qiao_id": character_qiao_id,
                "user_qiao_id": user_qiao_id,
                "role": AIContextRole.USER,
                "content": message_content,
            }
            context_id = await save_context_entry(db, context_data)

            if context_id is None:
                raise AIServiceError(
                    ai_service="context_management",
                    reason="save_failed",
                    message="Failed to save user message context",
                )

            logger.debug(
                "user_message_added_to_context",
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
                context_id=context_id,
                content_length=len(message_content),
            )

            return context_id

        except Exception as e:
            logger.error(
                "user_message_context_save_failed",
                error=str(e),
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
            )
            raise AIServiceError(
                ai_service="context_management",
                reason="save_failed",
                message=f"Failed to add user message to context: {str(e)}",
            )

    async def add_ai_response(
        self, db: AsyncSession, character_qiao_id: str, user_qiao_id: str, response_content: str
    ) -> int:
        """
        Add AI response to context.

        Args:
            db: Database session
            character_qiao_id: Character's qiao_id
            user_qiao_id: User's qiao_id
            response_content: AI response content

        Returns:
            Context ID of the saved entry

        Raises:
            AIServiceError: If saving fails
        """
        try:
            context_data = {
                "character_qiao_id": character_qiao_id,
                "user_qiao_id": user_qiao_id,
                "role": AIContextRole.ASSISTANT,
                "content": response_content,
            }
            context_id = await save_context_entry(db, context_data)

            if context_id is None:
                raise AIServiceError(
                    ai_service="context_management",
                    reason="save_failed",
                    message="Failed to save AI response context",
                )

            logger.debug(
                "ai_response_added_to_context",
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
                context_id=context_id,
                content_length=len(response_content),
            )

            return context_id

        except Exception as e:
            logger.error(
                "ai_response_context_save_failed",
                error=str(e),
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
            )
            raise AIServiceError(
                ai_service="context_management",
                reason="save_failed",
                message=f"Failed to add AI response to context: {str(e)}",
            )

    def _map_role_to_message_role(self, role: int) -> str:
        """
        Map context role enum to message role string.

        Args:
            role: Role enum value (1=user, 2=ai, 3=system)

        Returns:
            Message role string
        """
        # AIContextRole: 1=system, 2=user, 3=assistant
        role_mapping = {1: "system", 2: "user", 3: "assistant"}
        return role_mapping.get(role, "user")

    async def _merge_with_recent_messages(
        self, db: AsyncSession, character_qiao_id: str, user_qiao_id: str, new_content: str, role: int
    ) -> str:
        """
        Merge new message with recent messages if within time window.

        Args:
            db: Database session
            character_qiao_id: Character's qiao_id
            user_qiao_id: User's qiao_id
            new_content: New message content
            role: Message role

        Returns:
            Merged content or original content if no merge
        """
        try:
            # Get recent contexts within merge window
            # TODO: Implement message merging logic using cutoff_time for buffer mechanism
            cutoff_time = datetime.utcnow() - timedelta(seconds=self.merge_window_seconds)

            # For now, return original content as merging logic needs more complex implementation
            # This is a placeholder for the buffer mechanism described in the prototype
            logger.debug(
                "message_merge_check_completed",
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
                role=role,
                merge_window_seconds=self.merge_window_seconds,
            )

            return new_content

        except Exception as e:
            logger.error(
                "message_merge_failed",
                error=str(e),
                character_qiao_id=character_qiao_id,
                user_qiao_id=user_qiao_id,
            )
            # Return original content if merge fails
            return new_content


# Default context manager instance
default_context_manager = ContextManager()

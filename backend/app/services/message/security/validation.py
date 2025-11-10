"""
Message Validation Service

Validates message sending permissions based on bidirectional relationships
between users and AI characters. Implements the Block functionality design
from docs/prototype/message-flow.md (lines 486-554).
"""

from typing import Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from models.contact import Contact
from models.ai.character import AICharacter
from enums import ChatInfoType
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of message permission validation"""

    allowed: bool
    reason: Optional[str] = None
    chat_info_type: Optional[ChatInfoType] = None
    error_code: Optional[str] = None
    suggestions: Optional[list[str]] = None


class MessageValidationService:
    """
    Validates message sending permissions based on relationships.

    Implements three validation checks:
    1. User blocked AI character (contact.is_blocked)
    2. AI character blocked user (character.status == 3)
    3. Bidirectional relationship exists (character.user_qiao_id == user_qiao_id)
    """

    async def validate_message_permission(
        self, db: AsyncSession, from_qiao_id: str, character: AICharacter, contact: Contact
    ) -> ValidationResult:
        """
        Validate if user can send message to AI character.

        Args:
            db: Database session
            from_qiao_id: User's qiao_id
            character: AI character instance
            contact: Contact relationship instance

        Returns:
            ValidationResult with permission status and reason
        """
        # Check 1: User blocked AI character
        if contact.is_blocked:
            logger.info(
                "message_blocked_by_user",
                user_qiao_id=from_qiao_id,
                character_qiao_id=character.qiao_id,
                contact_id=contact.id,
            )
            return ValidationResult(
                allowed=False,
                reason="User has blocked this AI character",
                chat_info_type=ChatInfoType.MESSAGE_BLOCKED,
                error_code="USER_BLOCKED_CHARACTER",
            )

        # Check 2: AI character blocked user
        if character.status == 3:  # BLOCKED status
            logger.info(
                "message_blocked_by_character",
                user_qiao_id=from_qiao_id,
                character_qiao_id=character.qiao_id,
                character_status=character.status,
            )
            return ValidationResult(
                allowed=False,
                reason="AI character has blocked this user",
                chat_info_type=ChatInfoType.MESSAGE_BLOCKED,
                error_code="CHARACTER_BLOCKED_USER",
            )

        # Check 3: Bidirectional relationship (AI recognizes user)
        if character.user_qiao_id != from_qiao_id:
            logger.info(
                "bidirectional_relationship_missing",
                user_qiao_id=from_qiao_id,
                character_qiao_id=character.qiao_id,
                character_user_qiao_id=character.user_qiao_id,
            )
            return ValidationResult(
                allowed=False,
                reason=f"User '{from_qiao_id}' is not recognized by AI character '{character.qiao_id}' "
                f"(character.user_qiao_id={character.user_qiao_id or 'not set'})",
                chat_info_type=ChatInfoType.NOT_FRIEND,
                error_code="NOT_FRIEND",
                suggestions=[
                    "AI character needs to add you as friend",
                    "Contact relationship exists (User->AI) but AI doesn't recognize you (AI->User missing)",
                    "Both directions are required for normal chat functionality",
                ],
            )

        # All checks passed
        logger.debug(
            "message_permission_granted", user_qiao_id=from_qiao_id, character_qiao_id=character.qiao_id
        )
        return ValidationResult(allowed=True)

    async def validate_test_user_permission(
        self, db: AsyncSession, test_user_qiao_id: str, character: AICharacter, contact: Contact
    ) -> ValidationResult:
        """
        Validate test user permission for chat testing.

        Similar to validate_message_permission but with more detailed error messages
        for admin/testing purposes.

        Args:
            db: Database session
            test_user_qiao_id: Test user's qiao_id
            character: AI character instance
            contact: Contact relationship instance

        Returns:
            ValidationResult with permission status and detailed suggestions
        """
        # Check 1: User blocked AI character
        if contact.is_blocked:
            return ValidationResult(
                allowed=False,
                reason=f"Test user '{test_user_qiao_id}' has blocked AI character '{character.qiao_id}'",
                chat_info_type=ChatInfoType.MESSAGE_BLOCKED,
                error_code="TEST_USER_BLOCKED_CHARACTER",
                suggestions=[
                    "Unblock the AI character in Contacts management",
                    "Set contact.is_blocked = 0",
                ],
            )

        # Check 2: AI character blocked user
        if character.status == 3:  # BLOCKED status
            return ValidationResult(
                allowed=False,
                reason=f"AI character '{character.qiao_id}' has blocked test user '{test_user_qiao_id}'",
                chat_info_type=ChatInfoType.MESSAGE_BLOCKED,
                error_code="CHARACTER_BLOCKED_TEST_USER",
                suggestions=[
                    "Change character status from BLOCKED to ACTIVE",
                    "Check AI Character management to update status",
                ],
            )

        # Check 3: Bidirectional relationship
        if character.user_qiao_id != test_user_qiao_id:
            return ValidationResult(
                allowed=False,
                reason=f"Bidirectional relationship mismatch: Test user '{test_user_qiao_id}' has added "
                f"AI character '{character.qiao_id}' as contact, but AI character's owner is "
                f"'{character.user_qiao_id or 'not set'}' (expected: '{test_user_qiao_id}')",
                chat_info_type=ChatInfoType.NOT_FRIEND,
                error_code="OWNER_MISMATCH",
                suggestions=[
                    f"Set AI character's Owner User to test user ({test_user_qiao_id})",
                    "Or change the contact relationship to match the AI character's current owner",
                    "Both User->AI (contact) and AI->User (owner) relationships are required",
                ],
            )

        # All checks passed
        return ValidationResult(allowed=True)


# Global instance for dependency injection
message_validation_service = MessageValidationService()

# Export for easy import
__all__ = [
    "MessageValidationService",
    "ValidationResult",
    "message_validation_service",
]

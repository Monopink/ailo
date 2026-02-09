"""
Message Validation Service

Validates message sending permissions based on bidirectional relationships
between users and AI instances. Implements the Block functionality design
from docs/spec/message/special-types.md.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AIInstanceStatus, ChatInfoType
from app.models.ai.instance import AIInstance
from app.models.contact import Contact
from app.utils.logging import get_logger

logger = get_logger(__name__)
BLOCKED_STATUS = AIInstanceStatus.BLOCKED


@dataclass
class ValidationResult:
    """Result of message permission validation"""

    allowed: bool
    reason: str | None = None
    chat_info_type: ChatInfoType | None = None
    error_code: str | None = None
    suggestions: list[str] | None = None


class MessageValidationService:
    """
    Validates message sending permissions based on relationships.

    Implements two validation checks:
    1. User blocked AI instance (contact.is_blocked)
    2. AI instance blocked user (instance.status == 3)
    """

    async def validate_message_permission(
        self, db: AsyncSession, from_qiao_id: str, instance: AIInstance, contact: Contact
    ) -> ValidationResult:
        """
        Validate if user can send message to AI instance.

        Args:
            db: Database session
            from_qiao_id: User's qiao_id
            instance: AI instance
            contact: Contact relationship instance

        Returns:
            ValidationResult with permission status and reason
        """
        logger.debug(
            "message_permission_validation_started",
            db_session_id=id(db),
            user_qiao_id=from_qiao_id,
            instance_qiao_id=instance.qiao_id,
        )

        # Check 1: User blocked AI instance
        if contact.is_blocked:
            logger.info(
                "message_blocked_by_user",
                user_qiao_id=from_qiao_id,
                instance_qiao_id=instance.qiao_id,
                contact_id=contact.id,
            )
            return ValidationResult(
                allowed=False,
                reason="User has blocked this AI instance",
                chat_info_type=ChatInfoType.MESSAGE_BLOCKED,
                error_code="USER_BLOCKED_INSTANCE",
            )

        # Check 2: AI instance blocked user
        if instance.status == BLOCKED_STATUS:
            logger.info(
                "message_blocked_by_instance",
                user_qiao_id=from_qiao_id,
                instance_qiao_id=instance.qiao_id,
                instance_status=instance.status,
            )
            return ValidationResult(
                allowed=False,
                reason="AI instance has blocked this user",
                chat_info_type=ChatInfoType.MESSAGE_BLOCKED,
                error_code="INSTANCE_BLOCKED_USER",
            )

        # All checks passed
        logger.debug(
            "message_permission_granted",
            user_qiao_id=from_qiao_id,
            instance_qiao_id=instance.qiao_id,
        )
        return ValidationResult(allowed=True)

    async def validate_test_user_permission(
        self, db: AsyncSession, test_user_qiao_id: str, instance: AIInstance, contact: Contact
    ) -> ValidationResult:
        """
        Validate test user permission for chat testing.

        Similar to validate_message_permission but with more detailed error messages
        for admin/testing purposes.

        Args:
            db: Database session
            test_user_qiao_id: Test user's qiao_id
            instance: AI instance
            contact: Contact relationship instance

        Returns:
            ValidationResult with permission status and detailed suggestions
        """
        logger.debug(
            "test_user_permission_validation_started",
            db_session_id=id(db),
            test_user_qiao_id=test_user_qiao_id,
            instance_qiao_id=instance.qiao_id,
        )

        # Check 1: User blocked AI instance
        if contact.is_blocked:
            return ValidationResult(
                allowed=False,
                reason=(
                    f"Test user '{test_user_qiao_id}' has blocked AI instance '{instance.qiao_id}'"
                ),
                chat_info_type=ChatInfoType.MESSAGE_BLOCKED,
                error_code="TEST_USER_BLOCKED_INSTANCE",
                suggestions=[
                    "Unblock the AI instance in Contacts management",
                    "Set contact.is_blocked = 0",
                ],
            )

        # Check 2: AI instance blocked user
        if instance.status == BLOCKED_STATUS:
            return ValidationResult(
                allowed=False,
                reason=(
                    f"AI instance '{instance.qiao_id}' has blocked test user '{test_user_qiao_id}'"
                ),
                chat_info_type=ChatInfoType.MESSAGE_BLOCKED,
                error_code="INSTANCE_BLOCKED_TEST_USER",
                suggestions=[
                    "Change instance status from BLOCKED to ACTIVE",
                    "Check AI Instance management to update status",
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

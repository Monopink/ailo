"""
AI contact request handler.

This module handles contact requests for AI characters.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from models import AICharacter
from crud.ai import ai_character as ai_character_crud, ai_profile_template as ai_profile_template_crud
from utils.logging import get_logger

logger = get_logger(__name__)


class ContactRequestDecision:
    """Contact request decision result."""

    def __init__(self, accepted: bool, reason: str = ""):
        self.accepted = accepted
        self.reason = reason


async def handle_ai_contact_request(
    db: AsyncSession,
    *,
    request_id: int,
    from_qiao_id: str,
    to_qiao_id: str,
    message: str,
) -> ContactRequestDecision:
    """
    Handle contact request for AI character.

    This function determines whether an AI character should accept
    a contact request from a user.

    Args:
        db: Database session
        request_id: Contact request ID
        from_qiao_id: Requester's qiao_id
        to_qiao_id: AI character's qiao_id
        message: Request message from user

    Returns:
        ContactRequestDecision with accept/reject decision

    Raises:
        ValueError: If AI character not found or not available
    """
    # Validate AI profile template
    template = await ai_profile_template_crud.get_by_qiao_id(db, qiao_id=to_qiao_id)
    if not template:
        logger.error(
            "ai_template_not_found",
            request_id=request_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
        )
        # No response, similar to no one responding
        return ContactRequestDecision(accepted=False, reason="AI template not found")

    if template.status != 1:  # 1 = active
        logger.error(
            "ai_template_inactive",
            request_id=request_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            template_status=template.status,
        )
        # No response, similar to no one responding
        return ContactRequestDecision(accepted=False, reason="AI template not active")

    # MVP: Accept all requests by default
    # Future: Implement AI personality-based decision logic
    logger.info(
        "ai_contact_request_accepted",
        request_id=request_id,
        from_qiao_id=from_qiao_id,
        to_qiao_id=to_qiao_id,
    )

    return ContactRequestDecision(accepted=True)


# Future extension: AI personality-based decision
async def _evaluate_request_with_ai_personality(
    db: AsyncSession,
    ai_character: AICharacter,
    from_qiao_id: str,
    message: str,
) -> ContactRequestDecision:
    """
    Evaluate contact request based on AI personality.

    This is a placeholder for future implementation.
    Can use LLM to make decision based on:
    - AI character's personality
    - User's request message
    - User's history (if any)

    Args:
        db: Database session
        ai_character: AI character model
        from_qiao_id: Requester's qiao_id
        message: Request message

    Returns:
        ContactRequestDecision
    """
    # TODO: Implement LLM-based decision logic
    pass

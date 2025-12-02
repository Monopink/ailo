"""
Participant resolver for message storage.

Resolves qiao_id to participant type and ID.
"""

from crud.user import user as user_crud
from enums import MessageParticipantType
from models.ai.instance import AIInstance
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_participant_info(
    db: AsyncSession, qiao_id: str
) -> tuple[MessageParticipantType, int]:
    """
    Get participant type and ID from qiao_id.

    Args:
        db: Database session
        qiao_id: Participant's qiao_id

    Returns:
        Tuple of (participant_type, participant_id)

    Raises:
        ValueError: If participant not found
    """
    # System messages
    if qiao_id == "system":
        return MessageParticipantType.SYSTEM, 0

    # Try user
    user = await user_crud.get_by_qiao_id(db, qiao_id=qiao_id)
    if user:
        return MessageParticipantType.USER, user.id

    # Try AI instance
    result = await db.execute(select(AIInstance).where(AIInstance.qiao_id == qiao_id))
    instance = result.scalar_one_or_none()
    if instance:
        return MessageParticipantType.AI, instance.id

    # Not found
    logger.error("participant_not_found", qiao_id=qiao_id)
    raise ValueError(f"Participant not found: {qiao_id}")

"""
Conversation state API.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from core.database import get_db
from models.user import User
from schemas.conversation import ConversationStateResponse
from services.message.providers.leancloud import service as leancloud_service
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/conversation", tags=["Conversation"])


@router.get("/current", response_model=ConversationStateResponse)
async def get_current_conversation_state(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current IM conversation state (LeanCloud service conversation).

    Returns the provider conversation ID, version, and last update timestamp.
    """
    try:
        state = await leancloud_service.get_conversation_registry_state(db)
        logger.info(
            "conversation_state_retrieved",
            user_qiao_id=current_user.qiao_id,
            version=state["version"],
        )
        return state
    except Exception as error:
        logger.error(
            "conversation_state_failed",
            user_qiao_id=current_user.qiao_id,
            error=str(error),
            exc_info=True,
        )
        raise

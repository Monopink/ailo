"""System conversation registry endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from core.database import get_db
from models.user import User
from schemas.conversation import ConversationStateResponse
from services.message.providers.leancloud import service as leancloud_service
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["System Conversation"])


async def _get_system_conversation_state(
    current_user: User,
    db: AsyncSession,
) -> ConversationStateResponse:
    """Fetch LeanCloud system conversation identifier."""
    state = await leancloud_service.get_conversation_registry_state(db)
    logger.info(
        "system_conversation_state_retrieved",
        user_qiao_id=current_user.qiao_id,
        im_conv_id=state["im_conv_id"],
    )
    return state


@router.get("/system/lc-im-conversation", response_model=ConversationStateResponse, tags=["System"])
async def get_lc_im_conversation_state(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the current LeanCloud system conversation ID.

    The result is used by clients as the single source of truth for the IM provider conversation.
    """
    return await _get_system_conversation_state(current_user, db)


@router.get("/conversation/current", response_model=ConversationStateResponse, include_in_schema=False)
async def legacy_get_current_conversation_state(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Backward compatible endpoint for older clients."""
    return await _get_system_conversation_state(current_user, db)

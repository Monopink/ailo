"""
Bot-related API routes
"""

from fastapi import APIRouter, Depends, HTTPException
from ..auth import get_current_user
from ..services.bot_service import bot_service
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/bots", tags=["Bots"])


@router.get("")
async def get_bots(current_user: dict = Depends(get_current_user)):
    """
    Get current user's bots with their LeanMessage conversation IDs
    """
    try:
        user_entity_id = current_user.get("entity_id")
        if not user_entity_id:
            raise HTTPException(status_code=400, detail="User entity_id not found in token")

        bot_list = await bot_service.get_user_bots(user_entity_id)
        return {"status": "success", "data": bot_list}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_bots_endpoint_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{bot_id}")
async def get_bot(bot_id: int, current_user: dict = Depends(get_current_user)):
    """
    Get a specific bot by ID
    """
    try:
        bot = await bot_service.get_bot_by_id(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        return {"status": "success", "data": bot}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_bot_endpoint_error", error=str(e), bot_id=bot_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_id}")
async def get_bot_by_entity(entity_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get a specific bot by entity ID
    """
    try:
        bot = await bot_service.get_bot_by_entity_id(entity_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        return {"status": "success", "data": bot}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_bot_by_entity_endpoint_error", error=str(e), entity_id=entity_id)
        raise HTTPException(status_code=500, detail=str(e))

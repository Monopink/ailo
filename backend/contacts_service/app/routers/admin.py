"""
Admin-related API routes
"""

from fastapi import APIRouter, HTTPException
from ..services.leanmessage_manager import leanmessage_manager
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/setup-system-conversations")
async def setup_system_conversations():
    """
    Create LeanMessage system conversations for all bots
    """
    try:
        result = await leanmessage_manager.setup_bot_system_conversations()
        logger.info("setup_system_conversations_endpoint", result=result)

        return {"status": "success", "data": result}

    except Exception as e:
        logger.error("setup_system_conversations_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list-conversations")
async def list_conversations():
    """
    List all LeanMessage conversations
    """
    try:
        conversations = await leanmessage_manager.list_conversations()

        if conversations is None:
            raise HTTPException(status_code=500, detail="Failed to fetch conversations")

        # Categorize conversations
        system_convs = [c for c in conversations if c.get("sys", False)]
        normal_convs = [c for c in conversations if not c.get("sys", False)]

        return {
            "status": "success",
            "data": {
                "total": len(conversations),
                "system_conversations": len(system_convs),
                "normal_conversations": len(normal_convs),
                "conversations": conversations,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_conversations_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

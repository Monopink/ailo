from fastapi import APIRouter, HTTPException
from typing import Dict
from ....services.config_manager import get_unified_conversation_id

router = APIRouter()


@router.get("/conversation-id", summary="Get unified system conversation ID")
async def get_system_conversation_id() -> Dict[str, str]:
    """
    Get the unified system conversation ID used for all bot conversations.

    Returns:
        dict: {"conversation_id": "xxx"}

    Raises:
        HTTPException: 404 if conversation ID is not configured
        HTTPException: 500 for other errors
    """
    try:
        conversation_id = get_unified_conversation_id()
        return {"conversation_id": conversation_id}
    except ValueError:
        # Conversation ID not configured, try to create it
        try:
            from ....services.conversation_auto_setup import ensure_unified_conversation

            conversation_id = await ensure_unified_conversation()
            return {"conversation_id": conversation_id}
        except Exception as setup_error:
            raise HTTPException(
                status_code=503,
                detail=f"Unified conversation not configured and auto-creation failed: {str(setup_error)}. "
                "Please check LeanCloud credentials.",
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conversation ID: {str(e)}")

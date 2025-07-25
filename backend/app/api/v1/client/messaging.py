from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any

from services.message.providers.leancloud.conversation_manager import (
    get_leancloud_conversation_id,
    create_and_save_leancloud_conversation_id,
)
from services.message.providers.leancloud.health_checker import health_checker
from models.user import User
from api.deps import get_current_user
from core.database import SessionLocal
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/leancloud-conversation-id", summary="Get LeanCloud system conversation ID")
async def get_leancloud_conversation_id_endpoint(
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Get the LeanCloud system conversation ID used for all bot conversations.
    This endpoint is for frontend clients and requires JWT authentication.

    Returns:
        dict: {"conversation_id": "xxx"}

    Raises:
        HTTPException: 404 if conversation ID is not configured
        HTTPException: 500 for other errors
    """
    try:
        logger.info("leancloud_conversation_id_request", user_entity_id=current_user.entity_id)

        # Get conversation ID from database using new conversation_manager
        async with SessionLocal() as db:
            try:
                conversation_id = await get_leancloud_conversation_id(db)

                logger.info(
                    "leancloud_conversation_id_retrieved_for_frontend",
                    conversation_id=conversation_id,
                    user_entity_id=current_user.entity_id,
                )
                return {"conversation_id": conversation_id}

            except ValueError:
                # Conversation ID not configured, try to create one
                logger.info("leancloud_conversation_id_not_found_creating_new")

                conversation_id = await create_and_save_leancloud_conversation_id(db)

                logger.info(
                    "leancloud_conversation_id_created_and_saved",
                    conversation_id=conversation_id,
                    user_entity_id=current_user.entity_id,
                )
                return {"conversation_id": conversation_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_leancloud_conversation_id_error",
            error=str(e),
            user_entity_id=current_user.entity_id,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to get LeanCloud conversation ID")


@router.get("/health/leancloud-message-service", summary="LeanCloud message service health check")
async def get_leancloud_message_service_health() -> Dict[str, Any]:
    """
    Get LeanCloud message service health status.
    This endpoint does not require authentication and is used for monitoring.

    Returns:
        dict: Health status response in standard format
    """
    try:
        logger.info("leancloud_message_service_health_check_request")

        # Perform health check using new health checker
        health_status = await health_checker.check_leancloud_message_service_health()

        logger.info(
            "leancloud_message_service_health_check_response",
            service_status=health_status.get("leancloud_message_service"),
        )

        return health_status

    except Exception as e:
        logger.error("leancloud_message_service_health_check_endpoint_error", error=str(e), exc_info=True)
        return {
            "leancloud_message_service": "error",
            "leancloud_api": "error",
            "leancloud_conversation_id": "error",
            "details": {"error": f"Health check endpoint failed: {str(e)}"},
        }

"""
Messaging endpoints for frontend communication.
Provides conversation ID management and error reporting for frontend clients.
"""

import asyncio
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from pydantic import BaseModel, Field

from services.message.leancloud.db_config_manager import db_config_manager
from services.message.leancloud.config_migration import ensure_database_config_ready
from services.message.leancloud.conversation_notifier import conversation_notifier
from services.message.leancloud import conversation_logger, conversation_metrics
from models.user import User
from api.deps import get_current_user
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class ConversationErrorReport(BaseModel):
    """Frontend error report for conversation ID issues"""

    error_type: int = Field(..., description="Error type using numeric enum")
    conversation_id: str = Field(..., description="The conversation ID that failed")
    error_message: str = Field(..., description="Error message from frontend")
    timestamp: str = Field(..., description="ISO timestamp when error occurred")
    retry_count: int = Field(default=0, description="Number of retries attempted")
    user_agent: str = Field(default="", description="User agent for debugging")


class ConversationErrorType:
    """Error type enumeration using numeric values"""

    CONNECTION_FAILED = 1
    CONVERSATION_NOT_FOUND = 2
    PERMISSION_DENIED = 3
    TIMEOUT = 4
    UNKNOWN = 5


@router.get("/conversation-id", summary="Get unified system conversation ID")
async def get_conversation_id(current_user: User = Depends(get_current_user)) -> Dict[str, str]:
    """
    Get the unified system conversation ID used for all bot conversations.
    This endpoint is for frontend clients and requires JWT authentication.

    Returns:
        dict: {"conversation_id": "xxx"}

    Raises:
        HTTPException: 404 if conversation ID is not configured
        HTTPException: 500 for other errors
    """
    try:
        # Ensure database config is ready (migrate from file if needed)
        config_ready = await ensure_database_config_ready()
        if not config_ready:
            logger.warning("database_config_not_ready")

        # Get conversation ID from database
        conversation_id = await db_config_manager.get_unified_conversation_id()

        if conversation_id:
            logger.info(
                "conversation_id_retrieved_for_frontend",
                conversation_id=conversation_id,
                user_entity_id=current_user.entity_id,
            )
            return {"conversation_id": conversation_id}
        else:
            # Try to create conversation ID if not exists
            try:
                from ...services.message_service.leancloud.conversation_auto_setup import (
                    ensure_unified_conversation,
                )

                conversation_id = await ensure_unified_conversation()

                # Save to database
                await db_config_manager.set_unified_conversation_id(conversation_id)

                logger.info("conversation_id_created_and_saved", conversation_id=conversation_id)
                return {"conversation_id": conversation_id}

            except Exception as setup_error:
                logger.error("conversation_auto_setup_failed", error=str(setup_error))
                raise HTTPException(
                    status_code=503,
                    detail="Conversation ID not configured and auto-creation failed. Please contact support.",
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_conversation_id_error", error=str(e), user_entity_id=current_user.entity_id)
        raise HTTPException(status_code=500, detail="Failed to get conversation ID")


@router.get("/conversation-id/wait-update", summary="Wait for conversation ID update")
async def wait_conversation_id_update(
    timeout: int = 30, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Long polling endpoint to wait for conversation ID updates.
    Returns immediately if conversation ID is available, otherwise waits for update.

    Args:
        timeout: Maximum wait time in seconds (default: 30, max: 60)

    Returns:
        dict: {"conversation_id": "xxx", "updated": true/false}

    Raises:
        HTTPException: 408 if timeout occurs
        HTTPException: 500 for other errors
    """
    # Limit timeout to prevent resource exhaustion
    timeout = min(max(timeout, 5), 60)

    try:
        logger.info("conversation_id_wait_request", timeout=timeout, user_entity_id=current_user.entity_id)

        # Check if conversation ID is already available
        conversation_id = await db_config_manager.get_unified_conversation_id()
        if conversation_id:
            logger.info("conversation_id_immediately_available", conversation_id=conversation_id)
            return {"conversation_id": conversation_id, "updated": False}

        # Wait for conversation ID to be created/updated
        start_time = asyncio.get_event_loop().time()
        check_interval = 1.0  # Check every second

        while True:
            await asyncio.sleep(check_interval)

            # Check if conversation ID is now available
            conversation_id = await db_config_manager.get_unified_conversation_id()
            if conversation_id:
                logger.info(
                    "conversation_id_became_available",
                    conversation_id=conversation_id,
                    wait_time=asyncio.get_event_loop().time() - start_time,
                )
                return {"conversation_id": conversation_id, "updated": True}

            # Check timeout
            if asyncio.get_event_loop().time() - start_time >= timeout:
                logger.warning(
                    "conversation_id_wait_timeout",
                    timeout=timeout,
                    user_entity_id=current_user.entity_id,
                )
                raise HTTPException(status_code=408, detail="Timeout waiting for conversation ID update")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "wait_conversation_id_update_error", error=str(e), user_entity_id=current_user.entity_id
        )
        raise HTTPException(status_code=500, detail="Failed to wait for conversation ID update")


@router.post("/conversation-error-report", summary="Report conversation ID errors")
async def report_conversation_error(
    error_report: ConversationErrorReport, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Receive error reports from frontend about conversation ID issues.
    Logs errors for investigation and may trigger automatic recovery.

    Args:
        error_report: Error report from frontend

    Returns:
        dict: {"status": "received", "message": "...", "report_id": "..."}
    """
    try:
        user_entity_id = current_user.entity_id or "unknown"

        # Log the error report
        conversation_logger.log_frontend_error_report(
            error_type=error_report.error_type,
            conversation_id=error_report.conversation_id,
            error_message=error_report.error_message,
            user_entity_id=user_entity_id,
            retry_count=error_report.retry_count,
            user_agent=error_report.user_agent,
        )

        # Update metrics
        conversation_metrics.record_frontend_report(error_report.error_type)

        logger.info(
            "conversation_error_report_received",
            error_type=error_report.error_type,
            conversation_id=error_report.conversation_id,
            user_entity_id=user_entity_id,
            retry_count=error_report.retry_count,
        )

        # Trigger health check for critical errors
        if error_report.error_type in [
            ConversationErrorType.CONVERSATION_NOT_FOUND,
            ConversationErrorType.PERMISSION_DENIED,
        ]:
            logger.info("triggering_health_check_due_to_critical_error")
            from ....services.message.leancloud import health_checker

            # Perform health check in background
            asyncio.create_task(health_checker.perform_health_check())

        return {
            "status": "received",
            "message": "Error report logged for investigation",
            "report_id": f"{error_report.timestamp}_{error_report.error_type}_{user_entity_id}",
        }

    except Exception as e:
        logger.error(
            "error_processing_conversation_error_report",
            error=str(e),
            user_entity_id=current_user.entity_id,
        )
        raise HTTPException(status_code=500, detail="Failed to process error report")

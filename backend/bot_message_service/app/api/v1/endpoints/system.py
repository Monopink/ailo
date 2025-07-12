from fastapi import APIRouter, HTTPException, Header
from typing import Dict, Any
from pydantic import BaseModel, Field
from ....services.config_manager import get_unified_conversation_id
from ....utils.logging import get_logger
from ....services.leancloud import conversation_logger, conversation_metrics

logger = get_logger(__name__)

router = APIRouter()


class ConversationErrorReport(BaseModel):
    """Frontend error report for conversation ID issues"""

    error_type: int = Field(..., description="Error type using numeric enum for security")
    conversation_id: str = Field(..., description="The conversation ID that failed")
    error_message: str = Field(..., description="Error message from frontend")
    timestamp: str = Field(..., description="ISO timestamp when error occurred")
    retry_count: int = Field(default=0, description="Number of retries attempted")
    user_agent: str = Field(default="", description="User agent for debugging")


class ConversationErrorType:
    """Error type enumeration using numeric values for security"""

    CONNECTION_FAILED = 1
    CONVERSATION_NOT_FOUND = 2
    PERMISSION_DENIED = 3
    TIMEOUT = 4
    UNKNOWN = 5


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


@router.post("/conversation-error-report", summary="Report conversation ID errors from frontend")
async def report_conversation_error(error_report: ConversationErrorReport) -> Dict[str, Any]:
    """
    Receive error reports from frontend about conversation ID issues.

    This endpoint maintains distrust of frontend data while collecting useful debugging information.
    All frontend data is validated and logged but not automatically acted upon.

    Args:
        error_report: Error report from frontend

    Returns:
        dict: Acknowledgment response
    """
    try:
        # Log the error report with structured logging
        conversation_logger.log_frontend_error_report(
            error_type=error_report.error_type,
            conversation_id=error_report.conversation_id,
            error_message=error_report.error_message,
            retry_count=error_report.retry_count,
            user_agent=error_report.user_agent,
            timestamp=error_report.timestamp,
        )

        # Record metrics
        conversation_metrics.record_frontend_report(error_report.error_type)

        logger.warning(
            "frontend_conversation_error_reported",
            error_type=error_report.error_type,
            conversation_id=error_report.conversation_id,
            error_message=error_report.error_message,
            timestamp=error_report.timestamp,
            retry_count=error_report.retry_count,
            user_agent=error_report.user_agent,
        )

        # Validate error type is within expected range
        if error_report.error_type not in [1, 2, 3, 4, 5]:
            logger.warning(
                "invalid_error_type_reported",
                error_type=error_report.error_type,
                conversation_id=error_report.conversation_id,
            )

        # Validate conversation ID format (basic check)
        if not error_report.conversation_id or len(error_report.conversation_id) < 10:
            logger.warning(
                "suspicious_conversation_id_reported",
                conversation_id=error_report.conversation_id,
                error_type=error_report.error_type,
            )

        # Check if reported conversation ID matches our current one
        try:
            current_conversation_id = get_unified_conversation_id()
            if error_report.conversation_id != current_conversation_id:
                logger.warning(
                    "conversation_id_mismatch_reported",
                    reported_id=error_report.conversation_id,
                    current_id=current_conversation_id,
                    error_type=error_report.error_type,
                )
        except ValueError:
            logger.warning(
                "conversation_id_not_configured_during_error_report",
                reported_id=error_report.conversation_id,
            )

        # Trigger immediate health check if error seems critical
        if error_report.error_type in [
            ConversationErrorType.CONVERSATION_NOT_FOUND,
            ConversationErrorType.PERMISSION_DENIED,
        ]:
            logger.info("triggering_immediate_health_check_due_to_frontend_error")
            from ....services.leancloud import health_checker

            # Perform immediate health check (don't await to avoid blocking response)
            import asyncio

            asyncio.create_task(health_checker.perform_health_check())

        return {
            "status": "received",
            "message": "Error report logged for investigation",
            "report_id": f"{error_report.timestamp}_{error_report.error_type}",
        }

    except Exception as e:
        logger.error(
            "error_processing_frontend_report",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to process error report")


@router.post("/send-message", summary="Send system message (Internal API)")
async def send_system_message(
    request_data: Dict[str, Any], x_internal_key: str = Header(None)
) -> Dict[str, Any]:
    """
    Send system message to user (Internal API for service-to-service communication)

    Args:
        request_data: System message data containing from_entity, to_user, content
        x_internal_key: Internal service authentication key

    Returns:
        dict: Success response
    """
    try:
        # Verify internal service authentication
        from ....core.config import settings

        expected_key = getattr(settings, "INTERNAL_SERVICE_KEY", "default_internal_key_change_me")

        if not x_internal_key or x_internal_key != expected_key:
            raise HTTPException(
                status_code=403, detail="Forbidden: Invalid or missing internal service key"
            )

        from ....services.leanmessage import leanmessage_service

        from_entity = request_data.get("from_entity")
        to_user = request_data.get("to_user")
        content = request_data.get("content")
        message = request_data.get("message")

        if not all([from_entity, to_user, content]):
            raise HTTPException(
                status_code=400, detail="Missing required fields: from_entity, to_user, content"
            )

        # Type assertions for linter
        assert isinstance(from_entity, str), "from_entity must be string"
        assert isinstance(to_user, str), "to_user must be string"
        assert isinstance(content, dict), "content must be dictionary"

        await leanmessage_service.send_system_message(
            from_entity=from_entity, to_user=to_user, content=content, message=message
        )

        return {"status": "success", "message": "System message sent successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("send_system_message_api_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send system message: {str(e)}")

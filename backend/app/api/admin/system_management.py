"""
System management API endpoints for admin backend.

This module provides API endpoints for system-level operations like
refreshing LeanCloud system conversation and webhook management.
"""

import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from api.deps import get_db, verify_admin_session
from crud.system import system_configs
from enums import AdminOperationType
from services.message.providers.leancloud import service as leancloud_service
from utils.admin_logs import create_operation_log
from utils.logging import get_logger

logger = get_logger(__name__)

system_router = APIRouter()


@system_router.post("/leancloud/refresh-conversation")
async def refresh_leancloud_conversation(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: dict = Depends(verify_admin_session),
):
    """
    Refresh LeanCloud system conversation.

    Creates a new system conversation and updates the stored conversation_id.
    This endpoint should be used when the old conversation needs to be replaced.

    Returns:
        dict: Success status and new conversation_id or error message

    Example response (success):
        {
            "success": true,
            "conversation_id": "5a5d7432c3422b31ed845e75",
            "message": "System conversation refreshed successfully"
        }

    Example response (failure):
        {
            "success": false,
            "error": "LeanCloud configuration incomplete"
        }
    """
    logger.info(
        "admin_refresh_leancloud_conversation_requested",
        admin_user=admin_user["username"],
        admin_user_id=admin_user["id"],
    )

    try:
        success, result = await leancloud_service.refresh_system_conversation(db)

        if success:
            # Log success to database
            await create_operation_log(
                db=db,
                admin_user_id=admin_user["id"],
                operation_type=AdminOperationType.REFRESH,
                resource_type="leancloud_system",
                resource_id="system_conversation",
                resource_name="系统对话",
                operation_desc=f"刷新LeanCloud系统对话成功，新对话ID: {result}",
                request=request,
            )

            logger.info(
                "admin_refresh_leancloud_conversation_success",
                admin_user=admin_user["username"],
                conversation_id=result,
            )
            return {
                "success": True,
                "conversation_id": result,
                "message": "System conversation refreshed successfully",
            }
        else:
            # Log failure to database
            await create_operation_log(
                db=db,
                admin_user_id=admin_user["id"],
                operation_type=AdminOperationType.REFRESH,
                resource_type="leancloud_system",
                resource_id="system_conversation",
                resource_name="系统对话",
                operation_desc=f"刷新LeanCloud系统对话失败: {result}",
                request=request,
            )

            logger.error(
                "admin_refresh_leancloud_conversation_failed",
                admin_user=admin_user["username"],
                error=result,
            )
            return {"success": False, "error": result}

    except Exception as e:
        # Log exception to database
        try:
            await create_operation_log(
                db=db,
                admin_user_id=admin_user["id"],
                operation_type=AdminOperationType.REFRESH,
                resource_type="leancloud_system",
                resource_id="system_conversation",
                resource_name="系统对话",
                operation_desc=f"刷新LeanCloud系统对话异常: {str(e)}",
                request=request,
            )
        except Exception as log_error:
            logger.error(
                "failed_to_create_operation_log",
                error=str(log_error),
                exc_info=True,
            )

        logger.error(
            "admin_refresh_leancloud_conversation_error",
            admin_user=admin_user["username"],
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to refresh system conversation: {str(e)}")


# Removed: get_leancloud_conversation_status endpoint
# This endpoint only read database without business logic.
# Data is now loaded directly in template rendering.


@system_router.get("/leancloud-service-status")
async def get_leancloud_service_status(
    db: AsyncSession = Depends(get_db),
    admin_user: dict = Depends(verify_admin_session),
):
    """
    Get LeanCloud service status.

    Tests LeanCloud API connectivity and returns service reachability status.

    Returns:
        dict: Service status information

    Example response:
        {
            "success": true,
            "data": {
                "service_reachable": true,
                "last_check_time": "2025-10-15T10:30:00Z",
                "error_message": null
            }
        }
    """
    logger.info("admin_get_leancloud_service_status_requested", admin_user=admin_user["username"])

    try:
        from datetime import datetime, timezone
        from services.config import config_service

        # Get LeanCloud configuration
        leancloud_config = await config_service.get_leancloud_config(db)

        # Check if configuration is complete
        if not all(
            [
                leancloud_config.get("app_id"),
                leancloud_config.get("master_key"),
                leancloud_config.get("base_url"),
            ]
        ):
            return {
                "success": True,
                "data": {
                    "service_reachable": False,
                    "last_check_time": datetime.now(timezone.utc).isoformat(),
                    "error_message": "LeanCloud configuration incomplete",
                },
            }

        # Test LeanCloud API connectivity
        try:
            import httpx

            base_url = leancloud_config["base_url"]
            app_id = leancloud_config["app_id"]

            # Simple API test: get server time
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{base_url}/1.1/date", headers={"X-LC-Id": app_id})

                service_reachable = response.status_code == 200
                error_message = None if service_reachable else f"HTTP {response.status_code}"

        except Exception as e:
            service_reachable = False
            error_message = str(e)

        logger.info(
            "admin_get_leancloud_service_status_success",
            admin_user=admin_user["username"],
            service_reachable=service_reachable,
        )

        return {
            "success": True,
            "data": {
                "service_reachable": service_reachable,
                "last_check_time": datetime.now(timezone.utc).isoformat(),
                "error_message": error_message,
            },
        }

    except Exception as e:
        logger.error(
            "admin_get_leancloud_service_status_error", admin_user=admin_user["username"], error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to check service status: {str(e)}")


# Removed: get_webhook_url endpoint
# This endpoint only read database and construct URL string without business logic.
# Data is now loaded directly in template rendering.


@system_router.post("/regenerate-webhook-token")
async def regenerate_webhook_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: dict = Depends(verify_admin_session),
):
    """
    Regenerate webhook security token.

    Generates a new random token and updates the database.
    WARNING: After regenerating, you must update the webhook URL in LeanCloud console immediately.

    Returns:
        dict: Success status and warning message

    Example response:
        {
            "success": true,
            "message": "Webhook token regenerated successfully",
            "warning": "Please update the webhook URL in LeanCloud console immediately",
            "new_token_length": 43
        }
    """
    logger.info(
        "admin_regenerate_webhook_token_requested",
        admin_user=admin_user["username"],
        admin_user_id=admin_user["id"],
    )

    try:
        # Generate new token (43 characters)
        new_token = secrets.token_urlsafe(32)

        # Update database
        updated_config = await system_configs.update_config_value(
            db, config_key="leancloud_webhook_token", config_value=new_token, validate_enum=False
        )

        if not updated_config:
            logger.error(
                "webhook_token_update_failed",
                admin_user=admin_user["username"],
            )
            raise HTTPException(status_code=500, detail="Failed to update webhook token in database")

        # Log operation to database
        await create_operation_log(
            db=db,
            admin_user_id=admin_user["id"],
            operation_type=AdminOperationType.UPDATE,
            resource_type="leancloud_system",
            resource_id="webhook_token",
            resource_name="Webhook Token",
            operation_desc=f"重新生成Webhook Token (长度: {len(new_token)})",
            request=request,
        )

        logger.info(
            "admin_regenerate_webhook_token_success",
            admin_user=admin_user["username"],
            token_length=len(new_token),
        )

        return {
            "success": True,
            "message": "Webhook token regenerated successfully",
            "warning": "Please update the webhook URL in LeanCloud console immediately",
            "new_token_length": len(new_token),
        }

    except HTTPException:
        raise
    except Exception as e:
        # Log exception to database
        try:
            await create_operation_log(
                db=db,
                admin_user_id=admin_user["id"],
                operation_type=AdminOperationType.UPDATE,
                resource_type="leancloud_system",
                resource_id="webhook_token",
                resource_name="Webhook Token",
                operation_desc=f"重新生成Webhook Token失败: {str(e)}",
                request=request,
            )
        except Exception as log_error:
            logger.error(
                "failed_to_create_operation_log",
                error=str(log_error),
                exc_info=True,
            )

        logger.error(
            "admin_regenerate_webhook_token_error",
            admin_user=admin_user["username"],
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to regenerate webhook token: {str(e)}")

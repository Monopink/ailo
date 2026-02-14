"""System management API endpoints for admin backend.

This module provides API endpoints for system-level operations like
refreshing LeanCloud system conversation and webhook management.
"""

import secrets
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.deps import get_db, verify_admin_session
from app.crud.system import system_configs
from app.enums import AdminOperationType
from app.services.config import config_service
from app.services.message.providers.leancloud import service as leancloud_service
from app.utils.admin_logs import create_operation_log
from app.utils.logging import get_logger

logger = get_logger(__name__)

system_router = APIRouter()


@system_router.post("/leancloud/refresh-conversation")
async def refresh_leancloud_conversation(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> dict[str, Any]:
    """Refresh LeanCloud IM system conversation.

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
                resource_name="uni_conversation_id",
                operation_desc=(
                    "Refreshed LeanCloud system conversation successfully. "
                    f"New conversation ID: {result}"
                ),
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
        # Log failure to database
        await create_operation_log(
            db=db,
            admin_user_id=admin_user["id"],
            operation_type=AdminOperationType.REFRESH,
            resource_type="leancloud_system",
            resource_id="system_conversation",
            resource_name="uni_conversation_id",
            operation_desc=f"Failed to refresh LeanCloud system conversation: {result}",
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
                resource_name="uni_conversation_id",
                operation_desc=f"Exception while refreshing LeanCloud system conversation: {e!s}",
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
        raise HTTPException(status_code=500, detail="系统错误")


# Removed: get_leancloud_conversation_status endpoint
# This endpoint only read database without business logic.
# Data is now loaded directly in template rendering.


@system_router.get("/leancloud-service-status")
async def get_leancloud_service_status(
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> dict[str, Any]:
    """Get LeanCloud IM service status.

    Tests LeanCloud IM API connectivity and returns service reachability status.

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
        # Get LeanCloud IM configuration
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
                    "last_check_time": datetime.now(UTC).isoformat(),
                    "error_message": "LeanCloud IM configuration incomplete",
                },
            }

        # Test LeanCloud API connectivity
        try:
            base_url = leancloud_config["base_url"]
            app_id = leancloud_config["app_id"]

            if not isinstance(base_url, str) or not base_url:
                raise ValueError("Invalid LeanCloud base_url")
            if not isinstance(app_id, str) or not app_id:
                raise ValueError("Invalid LeanCloud app_id")

            # Simple API test: get server time
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{base_url}/1.1/date", headers={"X-LC-Id": app_id})

                service_reachable = response.status_code == HTTPStatus.OK
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
                "last_check_time": datetime.now(UTC).isoformat(),
                "error_message": error_message,
            },
        }

    except Exception as e:
        logger.error(
            "admin_get_leancloud_service_status_error",
            admin_user=admin_user["username"],
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="系统错误")


# Removed: get_webhook_url endpoint
# This endpoint only read database and construct URL string without business logic.
# Data is now loaded directly in template rendering.


@system_router.post("/regenerate-webhook-token")
async def regenerate_webhook_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> dict[str, Any]:
    """Regenerate LeanCloud IM webhook security token.

    Generates a new random token and updates the database.

    Warning:
        After regenerating, you must update the webhook URL in LeanCloud IM console immediately.

    Returns:
        dict: Success status and warning message

    Example response:
        {
            "success": true,
            "message": "Webhook token regenerated successfully",
            "warning": "Please update the webhook URL in LeanCloud console immediately",
            "new_token_length": 24
        }

    """
    logger.info(
        "admin_regenerate_webhook_token_requested",
        admin_user=admin_user["username"],
        admin_user_id=admin_user["id"],
    )

    try:
        # Generate new token (24 characters)
        new_token = secrets.token_urlsafe(18)

        # Update database
        updated_config = await system_configs.update_config_value(
            db, config_key="leancloud_im_webhook_token", config_value=new_token, validate_enum=False
        )

        if not updated_config:
            logger.error(
                "webhook_token_update_failed",
                admin_user=admin_user["username"],
            )
            raise HTTPException(status_code=500, detail="系统错误")

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
                operation_desc=f"重新生成Webhook Token失败: {e!s}",
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
        raise HTTPException(status_code=500, detail="系统错误")

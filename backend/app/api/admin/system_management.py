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
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.deps import get_db, verify_admin_session
from app.crud.system import system_configs
from app.enums import AdminOperationType, AdminRole
from app.enums.growth import (
    GrowthRewardRuleStatus,
    GrowthRewardScopeType,
    GrowthRewardTargetRole,
    GrowthRewardTriggerEvent,
)
from app.models.growth_reward import GrowthRewardRule
from app.services.entitlement.service import ENTITLEMENT_AI_CONTACT_LIMIT
from app.services.message.providers.leancloud import service as leancloud_service
from app.services.message.providers.leancloud.config import get_leancloud_runtime_config
from app.services.system_config import SystemConfigService
from app.utils.admin_logs import create_operation_log
from app.utils.logging import get_logger

logger = get_logger(__name__)

system_router = APIRouter()


class InvitationPolicyUpdateRequest(BaseModel):
    """Invitation policy payload for operation card editing."""

    invitee_reward_contact_delta: int = Field(ge=0)
    inviter_reward_contact_delta: int = Field(ge=0)
    inviter_max_rewards_per_actor: int | None = Field(default=None, ge=1)


def _require_admin_write_role(admin_user: dict[str, Any]) -> int:
    role_raw = admin_user.get("role")
    if isinstance(role_raw, bool) or not isinstance(role_raw, int | str):
        raise HTTPException(status_code=403, detail="Permission denied")
    try:
        role = int(role_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Permission denied") from exc
    if role not in (int(AdminRole.SUPER_ADMIN), int(AdminRole.ADMIN)):
        raise HTTPException(status_code=403, detail="Permission denied")
    return role


async def _get_invitation_reward_rule(
    db: AsyncSession,
    *,
    trigger_event: GrowthRewardTriggerEvent,
    target_role: GrowthRewardTargetRole,
    entitlement_type_id: int,
    for_update: bool,
) -> GrowthRewardRule:
    stmt = (
        select(GrowthRewardRule)
        .where(
            GrowthRewardRule.trigger_event == int(trigger_event),
            GrowthRewardRule.target_role == int(target_role),
            GrowthRewardRule.scope_type == int(GrowthRewardScopeType.GLOBAL),
            GrowthRewardRule.scope_id == 0,
            GrowthRewardRule.entitlement_type_id == entitlement_type_id,
            GrowthRewardRule.status == int(GrowthRewardRuleStatus.ACTIVE),
        )
        .order_by(GrowthRewardRule.priority.asc(), GrowthRewardRule.id.asc())
        .limit(1)
    )
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "Invitation reward rule not configured "
                f"(trigger_event={int(trigger_event)}, target_role={int(target_role)})"
            ),
        )
    return rule


async def _get_ai_contact_limit_entitlement_id(db: AsyncSession) -> int:
    result = await db.execute(
        text(
            """
            SELECT id FROM entitlement_types
            WHERE code = :code AND status = 1
            LIMIT 1
            """
        ),
        {"code": ENTITLEMENT_AI_CONTACT_LIMIT},
    )
    entitlement_id = result.scalar_one_or_none()
    if entitlement_id is None:
        raise HTTPException(status_code=500, detail="Entitlement type not configured")
    return int(entitlement_id)


@system_router.get("/invitation-policy")
async def get_invitation_policy(
    db: AsyncSession = Depends(get_db),
    _admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> dict[str, Any]:
    """Get invitation policy card data for operation settings."""
    _require_admin_write_role(_admin_user)
    try:
        entitlement_type_id = await _get_ai_contact_limit_entitlement_id(db)
        invitee_rule = await _get_invitation_reward_rule(
            db,
            trigger_event=GrowthRewardTriggerEvent.INVITE_BIND_SUCCESS,
            target_role=GrowthRewardTargetRole.INVITEE,
            entitlement_type_id=entitlement_type_id,
            for_update=False,
        )
        inviter_rule = await _get_invitation_reward_rule(
            db,
            trigger_event=GrowthRewardTriggerEvent.INVITE_BIND_SUCCESS,
            target_role=GrowthRewardTargetRole.INVITER,
            entitlement_type_id=entitlement_type_id,
            for_update=False,
        )
        return {
            "invitee_reward_contact_delta": int(invitee_rule.delta_granted),
            "inviter_reward_contact_delta": int(inviter_rule.delta_granted),
            "inviter_max_rewards_per_actor": (
                int(inviter_rule.max_rewards_per_actor)
                if inviter_rule.max_rewards_per_actor is not None
                else None
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_get_invitation_policy_failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="系统错误") from exc


@system_router.put("/invitation-policy")
async def update_invitation_policy(
    payload: InvitationPolicyUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> dict[str, Any]:
    """Update invitation policy from operation settings card."""
    _require_admin_write_role(admin_user)
    admin_user_id = int(admin_user["id"])
    try:
        entitlement_type_id = await _get_ai_contact_limit_entitlement_id(db)
        invitee_rule = await _get_invitation_reward_rule(
            db,
            trigger_event=GrowthRewardTriggerEvent.INVITE_BIND_SUCCESS,
            target_role=GrowthRewardTargetRole.INVITEE,
            entitlement_type_id=entitlement_type_id,
            for_update=True,
        )
        inviter_rule = await _get_invitation_reward_rule(
            db,
            trigger_event=GrowthRewardTriggerEvent.INVITE_BIND_SUCCESS,
            target_role=GrowthRewardTargetRole.INVITER,
            entitlement_type_id=entitlement_type_id,
            for_update=True,
        )

        invitee_rule.delta_granted = int(payload.invitee_reward_contact_delta)
        inviter_rule.delta_granted = int(payload.inviter_reward_contact_delta)
        inviter_rule.max_rewards_per_actor = (
            int(payload.inviter_max_rewards_per_actor)
            if payload.inviter_max_rewards_per_actor is not None
            else None
        )
        db.add(invitee_rule)
        db.add(inviter_rule)

        await db.commit()

        await create_operation_log(
            db=db,
            admin_user_id=admin_user_id,
            operation_type=AdminOperationType.UPDATE,
            resource_type="invitation_policy",
            resource_id="invitation_policy_card",
            resource_name="Invitation Policy Card",
            operation_desc="Updated invitation reward policy",
            request=request,
        )

        return {"success": True}
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.error("admin_update_invitation_policy_failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="系统错误") from exc


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
        leancloud_config = await get_leancloud_runtime_config(db, required=False)

        # Check if configuration is complete
        if not (
            leancloud_config.app_id and leancloud_config.master_key and leancloud_config.base_url
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
            base_url = leancloud_config.base_url
            app_id = leancloud_config.app_id

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

        await SystemConfigService.reload_cache(db)

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

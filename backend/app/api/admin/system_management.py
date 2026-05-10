"""System management API endpoints for admin backend."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.deps import get_db, verify_admin_session
from app.enums import AdminOperationType, AdminRole
from app.services.growth.invitation_policy import get_invitation_policy_rules
from app.utils.admin_logs import create_operation_log
from app.utils.logging import get_logger

logger = get_logger(__name__)

system_router = APIRouter()


class InvitationPolicyUpdateRequest(BaseModel):
    """Invitation policy payload for operation card editing."""

    invitee_reward_contact_delta: int = Field(ge=0)
    inviter_reward_contact_delta: int = Field(ge=0)
    inviter_max_rewards_per_actor: int | None = Field(default=None, ge=1)


def _extract_admin_role(admin_user: dict[str, Any]) -> int:
    role_raw = admin_user.get("role")
    if isinstance(role_raw, bool) or not isinstance(role_raw, int | str):
        raise HTTPException(status_code=403, detail="Permission denied")
    try:
        role = int(role_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Permission denied") from exc
    if role not in (int(AdminRole.SUPER_ADMIN), int(AdminRole.ADMIN), int(AdminRole.VIEWER)):
        raise HTTPException(status_code=403, detail="Permission denied")
    return role


def _require_admin_read_role(admin_user: dict[str, Any]) -> int:
    return _extract_admin_role(admin_user)


def _require_admin_write_role(admin_user: dict[str, Any]) -> int:
    role = _extract_admin_role(admin_user)
    if role not in (int(AdminRole.SUPER_ADMIN), int(AdminRole.ADMIN)):
        raise HTTPException(status_code=403, detail="Permission denied")
    return role


@system_router.get("/invitation-policy")
async def get_invitation_policy(
    db: AsyncSession = Depends(get_db),
    _admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> dict[str, Any]:
    """Get invitation policy card data for operation settings."""
    _require_admin_read_role(_admin_user)
    try:
        rules = await get_invitation_policy_rules(db, for_update=False)
        invitee_rule = rules.invitee_rule
        inviter_rule = rules.inviter_rule
        return {
            "invitee_reward_contact_delta": int(invitee_rule.delta_granted),
            "inviter_reward_contact_delta": int(inviter_rule.delta_granted),
            "inviter_max_rewards_per_actor": (
                int(inviter_rule.max_rewards_per_actor)
                if inviter_rule.max_rewards_per_actor is not None
                else None
            ),
        }
    except ValueError:
        logger.error("admin_get_invitation_policy_rule_invalid")
        raise HTTPException(status_code=500, detail="系统错误") from None
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
        rules = await get_invitation_policy_rules(db, for_update=True)
        invitee_rule = rules.invitee_rule
        inviter_rule = rules.inviter_rule

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
    except ValueError:
        await db.rollback()
        logger.error("admin_update_invitation_policy_rule_invalid")
        raise HTTPException(status_code=500, detail="系统错误") from None
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.error("admin_update_invitation_policy_failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="系统错误") from exc

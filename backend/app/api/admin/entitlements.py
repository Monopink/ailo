"""Admin entitlement operation APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_admin_session
from app.enums import AdminRole
from app.models.admin import AdminOperationLog
from app.schemas.admin import (
    AdminEntitlementOperationRequest,
    AdminEntitlementOperationResponse,
)
from app.services.entitlement.service import admin_operate_entitlement
from app.utils.client_ip import ClientIPResolutionError, get_client_ip
from app.utils.logging import get_logger

logger = get_logger(__name__)

entitlements_router = APIRouter(tags=["Admin Entitlements"])


def _require_admin_identity(
    admin_user: dict[str, Any], *, require_write: bool
) -> tuple[int, str, int]:
    raw_admin_id = admin_user.get("id")
    raw_username = admin_user.get("username")
    raw_role = admin_user.get("role")

    if isinstance(raw_admin_id, bool):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")
    if isinstance(raw_admin_id, int):
        admin_user_id = raw_admin_id
    elif isinstance(raw_admin_id, str) and raw_admin_id.strip() != "":
        try:
            admin_user_id = int(raw_admin_id.strip())
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="管理员身份无效",
            ) from exc
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")

    if not isinstance(raw_username, str) or raw_username.strip() == "":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")

    if isinstance(raw_role, bool):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")
    if isinstance(raw_role, int):
        role_value = raw_role
    elif isinstance(raw_role, str) and raw_role.strip() != "":
        try:
            role_value = int(raw_role.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="管理员身份无效",
            ) from exc
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")
    if role_value not in (int(AdminRole.SUPER_ADMIN), int(AdminRole.ADMIN), int(AdminRole.VIEWER)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")
    if require_write and role_value == int(AdminRole.VIEWER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理员无权限执行当前操作",
        )

    return admin_user_id, raw_username.strip(), role_value


@entitlements_router.post(
    "/operations",
    response_model=AdminEntitlementOperationResponse,
    summary="Grant or adjust user entitlement",
)
async def operate_user_entitlement(
    payload: AdminEntitlementOperationRequest,
    request: Request,
    admin_user: dict[str, Any] = Depends(verify_admin_session),
    db: AsyncSession = Depends(get_db),
) -> AdminEntitlementOperationResponse:
    """Execute one admin entitlement operation and persist audit log."""
    admin_user_id, admin_username, _admin_role = _require_admin_identity(
        admin_user, require_write=True
    )

    try:
        result = await admin_operate_entitlement(
            db,
            admin_user_id=admin_user_id,
            user_id=payload.user_id,
            entitlement_type_code=payload.entitlement_type_code.strip(),
            operation_type=payload.operation_type,
            delta=payload.delta,
            reason_code=payload.reason_code.strip(),
            idempotency_key=payload.idempotency_key.strip(),
            remark=payload.remark.strip(),
        )

        ip_address: str | None = None
        try:
            ip_address = get_client_ip(request)
        except ClientIPResolutionError:
            ip_address = None

        operation_desc = (
            f"{payload.operation_type} entitlement user={payload.user_id} "
            f"type={payload.entitlement_type_code} delta={payload.delta} "
            f"reason={payload.reason_code}"
        )
        db.add(
            AdminOperationLog(
                admin_user_id=admin_user_id,
                operation_type=2,
                resource_type="entitlement",
                resource_id=str(payload.user_id),
                resource_name=payload.entitlement_type_code,
                operation_desc=operation_desc,
                ip_address=ip_address,
                user_agent=request.headers.get("user-agent", ""),
            )
        )
        await db.commit()

        account = result.account
        return AdminEntitlementOperationResponse(
            accepted=True,
            applied=result.applied,
            user_id=payload.user_id,
            entitlement_type_code=payload.entitlement_type_code,
            action_type=result.action_type,
            delta_granted=result.delta_granted,
            delta_used=result.delta_used,
            source_type=result.source_type,
            reason_code=result.reason_code,
            idempotency_key=result.idempotency_key,
            granted_total=account.granted_total if account else None,
            used_total=account.used_total if account else None,
            available_total=account.available_total if account else None,
            version=account.version if account else None,
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:  # pragma: no cover - runtime protection
        await db.rollback()
        logger.error(
            "admin_entitlement_operation_failed",
            admin_user_id=admin_user_id,
            admin_username=admin_username,
            user_id=payload.user_id,
            entitlement_type_code=payload.entitlement_type_code,
            operation_type=payload.operation_type,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        ) from exc

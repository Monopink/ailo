"""Admin entitlement operation APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import get_db, verify_admin_session
from app.crud.entitlement import entitlement_type as entitlement_type_crud
from app.crud.entitlement import user_entitlement_account as user_entitlement_account_crud
from app.enums import AdminRole, UserStatus
from app.models.admin import AdminOperationLog
from app.models.entitlement import EntitlementType, UserEntitlementAccount
from app.models.user import User
from app.schemas.admin import (
    AdminEntitlementOperationRequest,
    AdminEntitlementOperationResponse,
)
from app.services.entitlement.service import admin_operate_entitlement
from app.utils.client_ip import ClientIPResolutionError, get_client_ip
from app.utils.email import mask_email
from app.utils.logging import get_logger
from app.utils.phone import mask_phone
from app.utils.user_display import build_masked_user_display_label

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


def _parse_positive_user_id(raw_user_id: str) -> int:
    user_id_str = raw_user_id.strip()
    if user_id_str == "" or not user_id_str.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户ID参数无效")
    user_id = int(user_id_str)
    if user_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户ID参数无效")
    return user_id


@entitlements_router.get(
    "/users/search",
    summary="Search users for entitlement operations",
)
async def search_users_for_entitlement_operations(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
    page: int = Query(default=1, ge=1, le=200),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Search users by id/username/phone/email for operation form selection."""
    _require_admin_identity(admin_user, require_write=False)
    query = q.strip()
    if query == "":
        return {"items": []}

    conditions: list[ColumnElement[bool]] = []
    if query.isdigit():
        try:
            conditions.append(User.id == int(query))
        except ValueError:
            pass
        conditions.append(User.phone.ilike(f"%{query}%"))
    elif "@" in query:
        conditions.append(User.email.ilike(f"{query}%"))
    else:
        conditions.append(User.username.ilike(f"{query}%"))
        digits = "".join(ch for ch in query if ch.isdigit())
        if digits != "":
            conditions.append(User.phone.ilike(f"%{digits}%"))

    if len(conditions) == 0:
        return {"items": []}

    offset = (page - 1) * limit

    stmt = (
        select(User.id, User.username, User.phone, User.email)
        .where(
            User.status == int(UserStatus.ACTIVE),
            or_(*conditions),
        )
        .order_by(User.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    result = await db.execute(stmt)
    rows = result.all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = []
    for row in rows:
        user_id = int(row[0])
        username = row[1] if isinstance(row[1], str) else None
        phone = row[2] if isinstance(row[2], str) else None
        email = row[3] if isinstance(row[3], str) else None
        display_label = build_masked_user_display_label(
            user_id=user_id,
            username=username,
            phone=phone,
            email=email,
        )
        items.append(
            {
                "id": str(user_id),
                "text": display_label,
                "meta": {
                    "user_id": str(user_id),
                    "username": username,
                    "phone": mask_phone(phone) if phone is not None else None,
                    "email": mask_email(email) if email is not None else None,
                },
            }
        )
    return {"items": items, "has_more": has_more}


@entitlements_router.get(
    "/users/assets",
    summary="Get all entitlement assets for one user",
)
async def get_user_entitlement_assets(
    user_id: int = Query(..., ge=1),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return all active entitlement assets for one user."""
    _require_admin_identity(admin_user, require_write=False)

    user_exists_result = await db.execute(select(User.id).where(User.id == user_id).limit(1))
    if user_exists_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    entitlement_types_result = await db.execute(
        select(EntitlementType.id, EntitlementType.code)
        .where(EntitlementType.status == 1)
        .order_by(EntitlementType.code.asc())
    )
    entitlement_type_rows = entitlement_types_result.all()
    type_id_by_code = {str(row[1]): int(row[0]) for row in entitlement_type_rows}
    entitlement_type_ids = list(type_id_by_code.values())

    account_by_type_id: dict[int, Any] = {}
    if entitlement_type_ids:
        accounts_result = await db.execute(
            select(UserEntitlementAccount).where(
                UserEntitlementAccount.user_id == user_id,
                UserEntitlementAccount.entitlement_type_id.in_(entitlement_type_ids),
            )
        )
        account_by_type_id = {
            int(account.entitlement_type_id): account for account in accounts_result.scalars().all()
        }

    items: list[dict[str, Any]] = []
    for code, entitlement_type_id in type_id_by_code.items():
        account = account_by_type_id.get(entitlement_type_id)
        if account is None:
            items.append(
                {
                    "entitlement_type_code": code,
                    "account_exists": False,
                    "granted_total": 0,
                    "used_total": 0,
                    "available_total": 0,
                    "version": 0,
                }
            )
            continue
        items.append(
            {
                "entitlement_type_code": code,
                "account_exists": True,
                "granted_total": int(account.granted_total),
                "used_total": int(account.used_total),
                "available_total": int(account.available_total),
                "version": int(account.version),
            }
        )
    return {"user_id": user_id, "items": items}


@entitlements_router.get(
    "/account-snapshot",
    summary="Get entitlement account snapshot for operation preview",
)
async def get_entitlement_account_snapshot(
    user_id: int = Query(..., ge=1),
    entitlement_type_code: str = Query(..., min_length=1, max_length=64),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return current account totals for one user/type pair."""
    _require_admin_identity(admin_user, require_write=False)
    normalized_type_code = entitlement_type_code.strip()
    if normalized_type_code == "":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="权益类型参数无效")

    user_exists_result = await db.execute(select(User.id).where(User.id == user_id).limit(1))
    if user_exists_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    entitlement_type = await entitlement_type_crud.get_by_code(db, code=normalized_type_code)
    if entitlement_type is None or int(entitlement_type.status) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="权益类型不存在或未启用",
        )

    account = await user_entitlement_account_crud.get_by_user_and_type(
        db,
        user_id=user_id,
        entitlement_type_id=int(entitlement_type.id),
        for_update=False,
    )
    if account is None:
        return {
            "user_id": user_id,
            "entitlement_type_code": normalized_type_code,
            "account_exists": False,
            "granted_total": 0,
            "used_total": 0,
            "available_total": 0,
            "version": 0,
        }
    return {
        "user_id": user_id,
        "entitlement_type_code": normalized_type_code,
        "account_exists": True,
        "granted_total": int(account.granted_total),
        "used_total": int(account.used_total),
        "available_total": int(account.available_total),
        "version": int(account.version),
    }


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
    target_user_id = _parse_positive_user_id(payload.user_id)
    user_exists_result = await db.execute(select(User.id).where(User.id == target_user_id).limit(1))
    if user_exists_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户不存在")

    entitlement_type_code = payload.entitlement_type_code.strip()
    reason_code = payload.reason_code.strip()
    idempotency_key = payload.idempotency_key.strip()
    remark = payload.remark.strip() if isinstance(payload.remark, str) else None

    try:
        result = await admin_operate_entitlement(
            db,
            admin_user_id=admin_user_id,
            user_id=target_user_id,
            entitlement_type_code=entitlement_type_code,
            operation_type=payload.operation_type,
            delta=payload.delta,
            reason_code=reason_code,
            idempotency_key=idempotency_key,
            remark=remark,
        )

        ip_address: str | None = None
        try:
            ip_address = get_client_ip(request)
        except ClientIPResolutionError:
            ip_address = None

        operation_desc = (
            f"Admin entitlement {payload.operation_type} "
            f"user={target_user_id} type={entitlement_type_code} delta={payload.delta}"
        )
        db.add(
            AdminOperationLog(
                admin_user_id=admin_user_id,
                operation_type=2,
                resource_type="entitlement_operation",
                resource_id=str(target_user_id),
                resource_name=entitlement_type_code,
                operation_desc=operation_desc,
                operation_meta={
                    "operation_type": payload.operation_type,
                    "user_id": target_user_id,
                    "entitlement_type_code": entitlement_type_code,
                    "delta": payload.delta,
                    "reason_code": reason_code,
                    "applied": result.applied,
                    "idempotency_key": idempotency_key,
                },
                ip_address=ip_address,
                user_agent=request.headers.get("user-agent", ""),
            )
        )
        await db.commit()

        account = result.account
        return AdminEntitlementOperationResponse(
            accepted=True,
            applied=result.applied,
            user_id=target_user_id,
            entitlement_type_code=entitlement_type_code,
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
            user_id=target_user_id,
            entitlement_type_code=payload.entitlement_type_code,
            operation_type=payload.operation_type,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        ) from exc

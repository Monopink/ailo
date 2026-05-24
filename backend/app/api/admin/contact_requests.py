from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user_and_db
from app.enums import AdminRole, ContactRequestRetryMode
from app.schemas.contact import ContactRequestRetryPayload, ContactRequestRetryPrecheckPayload
from app.services.contact.incomplete_admin_service import (
    admin_ignore_incomplete_contact_request,
    admin_reopen_ignored_contact_request,
    get_incomplete_contact_request_overview,
    list_incomplete_contact_requests,
    parse_contact_request_id_or_400,
)
from app.services.contact.incomplete_retry_service import (
    parse_ai_type_id_or_400,
    parse_template_id_or_400,
    precheck_incomplete_contact_request_retry,
    retry_incomplete_contact_request,
    search_ai_types_for_retry,
    search_templates_for_retry,
)
from app.type_defs import JSONDict

contact_requests_router = APIRouter(tags=["Admin Contact Requests"])


def _require_admin_identity(
    admin_user: dict[str, Any], *, require_super_admin: bool
) -> tuple[int, str, int]:
    raw_admin_id = admin_user.get("id")
    raw_username = admin_user.get("username")
    raw_role = admin_user.get("role")

    if isinstance(raw_admin_id, bool):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")
    if isinstance(raw_admin_id, int):
        admin_user_id = raw_admin_id
    elif isinstance(raw_admin_id, str) and raw_admin_id.strip().isdigit():
        admin_user_id = int(raw_admin_id.strip())
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")
    if admin_user_id <= 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")

    if not isinstance(raw_username, str) or raw_username.strip() == "":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")
    username = raw_username.strip()

    if isinstance(raw_role, bool):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")
    if isinstance(raw_role, int):
        role_value = raw_role
    elif isinstance(raw_role, str) and raw_role.strip().isdigit():
        role_value = int(raw_role.strip())
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")

    if role_value not in (int(AdminRole.SUPER_ADMIN), int(AdminRole.ADMIN), int(AdminRole.VIEWER)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员身份无效")
    if require_super_admin and role_value != int(AdminRole.SUPER_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理员无权限执行当前操作",
        )

    return admin_user_id, username, role_value


@contact_requests_router.get(
    "/incomplete/overview",
    summary="Get incomplete contact request overview",
)
async def admin_get_incomplete_contact_request_overview(
    admin_context: tuple[dict[str, Any], AsyncSession] = Depends(get_admin_user_and_db),
) -> JSONDict:
    """Get overview metrics for incomplete contact request panel."""
    _, db = admin_context
    return await get_incomplete_contact_request_overview(db)


@contact_requests_router.get("/incomplete", summary="List incomplete contact requests")
async def admin_list_incomplete_contact_requests(
    ai_type_id: str | None = Query(default=None),
    failure_code: str | None = Query(default=None),
    status_filter: int | None = Query(default=None, alias="status"),
    updated_from: datetime | None = Query(default=None),
    updated_to: datetime | None = Query(default=None),
    limit: int | None = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin_context: tuple[dict[str, Any], AsyncSession] = Depends(get_admin_user_and_db),
) -> JSONDict:
    """List incomplete contact requests for admin panel."""
    _, db = admin_context
    return await list_incomplete_contact_requests(
        db,
        ai_type_id=ai_type_id,
        failure_code=failure_code,
        status=status_filter,
        updated_from=updated_from,
        updated_to=updated_to,
        limit=limit,
        offset=offset,
    )


@contact_requests_router.get(
    "/templates/search", summary="Search templates for contact request retry"
)
async def admin_search_templates_for_retry(
    q: str = Query(default="", max_length=100),
    ai_type_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    page: int = Query(default=1, ge=1, le=200),
    admin_context: tuple[dict[str, Any], AsyncSession] = Depends(get_admin_user_and_db),
) -> JSONDict:
    """Search templates for selected-template retry modal."""
    admin_user, db = admin_context
    _require_admin_identity(admin_user, require_super_admin=False)
    return await search_templates_for_retry(
        db,
        query=q,
        limit=limit,
        page=page,
        ai_type_id=parse_ai_type_id_or_400(ai_type_id) if ai_type_id is not None else None,
    )


@contact_requests_router.get(
    "/ai-types/search", summary="Search AI types for manual contact request retry"
)
async def admin_search_ai_types_for_retry(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
    page: int = Query(default=1, ge=1, le=200),
    admin_context: tuple[dict[str, Any], AsyncSession] = Depends(get_admin_user_and_db),
) -> JSONDict:
    """Search AI types for manual retry modal."""
    admin_user, db = admin_context
    _require_admin_identity(admin_user, require_super_admin=False)
    return await search_ai_types_for_retry(
        db,
        query=q,
        limit=limit,
        page=page,
    )


@contact_requests_router.post(
    "/{request_id}/retry-precheck", summary="Precheck incomplete AI contact request retry"
)
async def admin_precheck_contact_request_retry(
    request_id: str,
    payload: ContactRequestRetryPrecheckPayload | None = None,
    admin_context: tuple[dict[str, Any], AsyncSession] = Depends(get_admin_user_and_db),
) -> JSONDict:
    """Run precheck for auto/template retry and return risk report."""
    parsed_request_id = parse_contact_request_id_or_400(request_id)
    admin_user, db = admin_context
    _require_admin_identity(admin_user, require_super_admin=False)

    retry_mode = payload.mode if payload is not None else ContactRequestRetryMode.AUTO
    selected_ai_type_id = (
        parse_ai_type_id_or_400(payload.selected_ai_type_id)
        if payload is not None and payload.selected_ai_type_id is not None
        else None
    )
    selected_template_id = (
        parse_template_id_or_400(payload.selected_template_id)
        if payload is not None and payload.selected_template_id is not None
        else None
    )
    if retry_mode == ContactRequestRetryMode.MANUAL:
        _require_admin_identity(admin_user, require_super_admin=True)
    return await precheck_incomplete_contact_request_retry(
        db,
        request_id=parsed_request_id,
        mode=retry_mode,
        selected_ai_type_id=selected_ai_type_id,
        selected_template_id=selected_template_id,
    )


@contact_requests_router.post("/{request_id}/retry", summary="Retry incomplete AI contact request")
async def admin_retry_contact_request(
    request_id: str,
    payload: ContactRequestRetryPayload,
    admin_context: tuple[dict[str, Any], AsyncSession] = Depends(get_admin_user_and_db),
) -> JSONDict:
    """Retry an incomplete AI contact request.

    Args:
        request_id: ID of the contact request to retry
        payload: Optional payload with alias and tags to override
        admin_context: Admin user session and database connection

    Returns:
        Retry execution result payload

    """
    parsed_request_id = parse_contact_request_id_or_400(request_id)
    admin_user, db = admin_context
    admin_user_id, username, _ = _require_admin_identity(admin_user, require_super_admin=False)
    retry_mode = payload.mode
    if retry_mode == ContactRequestRetryMode.MANUAL:
        _require_admin_identity(admin_user, require_super_admin=True)

    parsed_selected_ai_type_id = (
        parse_ai_type_id_or_400(payload.selected_ai_type_id)
        if payload.selected_ai_type_id is not None
        else None
    )
    parsed_selected_template_id = (
        parse_template_id_or_400(payload.selected_template_id)
        if payload.selected_template_id is not None
        else None
    )
    return await retry_incomplete_contact_request(
        db,
        request_id=parsed_request_id,
        mode=retry_mode,
        selected_ai_type_id=parsed_selected_ai_type_id,
        selected_template_id=parsed_selected_template_id,
        force_continue=payload.force_continue,
        idempotency_key=payload.idempotency_key,
        precheck_payload=payload.precheck_payload,
        alias=payload.alias,
        tags=payload.tags,
        operator_admin_user_id=admin_user_id,
        operator=username,
    )


@contact_requests_router.post(
    "/{request_id}/ignore",
    summary="Ignore incomplete contact request from admin panel",
)
async def admin_ignore_incomplete_request(
    request_id: str,
    admin_context: tuple[dict[str, Any], AsyncSession] = Depends(get_admin_user_and_db),
) -> JSONDict:
    """Set incomplete request status to IGNORED for admin operations."""
    parsed_request_id = parse_contact_request_id_or_400(request_id)
    admin_user, db = admin_context
    admin_user_id, username, role_value = _require_admin_identity(
        admin_user, require_super_admin=False
    )
    return await admin_ignore_incomplete_contact_request(
        db,
        request_id=parsed_request_id,
        operator_admin_user_id=admin_user_id,
        operator_username=username,
        operator_role=role_value,
    )


@contact_requests_router.post(
    "/{request_id}/reopen-pending",
    summary="Reopen ignored contact request to pending",
)
async def admin_reopen_ignored_request(
    request_id: str,
    admin_context: tuple[dict[str, Any], AsyncSession] = Depends(get_admin_user_and_db),
) -> JSONDict:
    """Set ignored request status to PENDING for admin operations."""
    parsed_request_id = parse_contact_request_id_or_400(request_id)
    admin_user, db = admin_context
    admin_user_id, username, role_value = _require_admin_identity(
        admin_user, require_super_admin=False
    )
    return await admin_reopen_ignored_contact_request(
        db,
        request_id=parsed_request_id,
        operator_admin_user_id=admin_user_id,
        operator_username=username,
        operator_role=role_value,
    )

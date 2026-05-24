"""Admin-facing incomplete contact request query services."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.enums import (
    AdminOperationType,
    AdminRole,
    ContactRequestFailureCode,
    ContactRequestRetryFailureCode,
    ContactRequestRetryResultStatus,
    ContactRequestStatus,
    ContactType,
)
from app.models.ai.template import AIPersona, AIType
from app.models.contact import ContactRequest, ContactRequestRetryAttempt
from app.type_defs import JSONDict, JSONValue
from app.utils.admin_logs import create_operation_log

_SNOWFLAKE_PATTERN = re.compile(r"^[0-9]+$")
_MAX_LIMIT = 100
_DEFAULT_LIMIT = 20
_RETRY_FAILED_STATUSES = (
    ContactRequestRetryResultStatus.FAILED.value,
    ContactRequestRetryResultStatus.ERROR.value,
)
_INCOMPLETE_STATUSES = (
    int(ContactRequestStatus.PENDING),
    int(ContactRequestStatus.PROCESSING),
    int(ContactRequestStatus.FAILED),
)


@dataclass(frozen=True)
class FailureCodeMeta:
    """Human-readable metadata for failure code display."""

    label: str
    hint: str


_FAILURE_META_MAP: dict[str, FailureCodeMeta] = {
    ContactRequestFailureCode.NO_TEMPLATE_AVAILABLE.value: FailureCodeMeta(
        label="当前类型缺少可用模板",
        hint="请补充该类型可用模板后重试",
    ),
    ContactRequestFailureCode.ALL_TEMPLATES_ALREADY_USED.value: FailureCodeMeta(
        label="当前用户已用尽该类型可选模板",
        hint="请新增可用模板后重试",
    ),
    ContactRequestFailureCode.MANUAL_PROVISION_REQUIRED.value: FailureCodeMeta(
        label="该请求需要人工补充模板后处理",
        hint="请补模板后重试",
    ),
}


def parse_contact_request_id_or_400(raw_request_id: str) -> int:
    """Parse contact request Snowflake ID from path parameter."""
    candidate = raw_request_id.strip()
    if not candidate or not _SNOWFLAKE_PATTERN.fullmatch(candidate):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    request_id = int(candidate)
    if request_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    return request_id


def normalize_dt_utc(value: datetime | None) -> datetime | None:
    """Normalize datetime input into UTC timezone-aware value."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_page_limit(limit: int | None) -> int:
    """Normalize pagination limit."""
    if limit is None:
        return _DEFAULT_LIMIT
    return max(1, min(limit, _MAX_LIMIT))


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _to_str_id(value: int | None) -> str | None:
    return str(value) if value is not None else None


def _extract_ai_type_id(detail: JSONDict | None) -> str | None:
    if detail is None:
        return None
    ai_type = detail.get("ai_type_id")
    if ai_type is None:
        ai_type = detail.get("type_id")
    if ai_type is None:
        return None
    return str(ai_type)


def _parse_positive_int(raw_value: object) -> int | None:
    if isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, int):
        return raw_value if raw_value > 0 else None
    if isinstance(raw_value, str):
        candidate = raw_value.strip()
        if candidate.isdigit():
            parsed = int(candidate)
            return parsed if parsed > 0 else None
    return None


def _failure_meta(code: str | None) -> FailureCodeMeta:
    if not isinstance(code, str):
        return FailureCodeMeta(label="未知失败原因", hint="请查看失败详情并人工排查")
    return _FAILURE_META_MAP.get(
        code,
        FailureCodeMeta(label=f"未收录失败码：{code}", hint="请查看失败详情并人工排查"),
    )


def _is_retryable(code: str | None) -> bool:
    return isinstance(code, str) and code in _FAILURE_META_MAP


def _is_retryable_request(*, status_value: int | None, failure_code: str | None) -> bool:
    if status_value == ContactRequestStatus.FAILED:
        return True
    return status_value == ContactRequestStatus.PENDING and _is_retryable(failure_code)


def _base_incomplete_panel_conditions() -> list[ColumnElement[bool]]:
    return [ContactRequest.status.in_(_INCOMPLETE_STATUSES)]


def _assert_admin_can_write(role_value: int) -> None:
    if role_value == int(AdminRole.VIEWER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理员无权限执行当前操作",
        )


async def _load_ai_type_name_map(db: AsyncSession, *, ai_type_ids: set[str]) -> dict[str, str]:
    int_ids: list[int] = []
    for raw_id in ai_type_ids:
        if raw_id.isdigit():
            int_ids.append(int(raw_id))
    if not int_ids:
        return {}

    result = await db.execute(select(AIType.id, AIType.display_name).where(AIType.id.in_(int_ids)))
    return {str(row.id): row.display_name for row in result}


async def _build_reopen_failure_detail_for_ai_request(
    db: AsyncSession, *, request_row: ContactRequest
) -> JSONDict:
    detail = request_row.failure_detail if isinstance(request_row.failure_detail, dict) else {}
    ai_type_id = _parse_positive_int(detail.get("ai_type_id") or detail.get("type_id"))
    qiao_id = detail.get("qiao_id")

    if ai_type_id is None:
        persona_result = await db.execute(
            select(AIPersona.type_id, AIPersona.qiao_id).where(
                AIPersona.qiao_id == request_row.to_qiao_id
            )
        )
        persona_row = persona_result.one_or_none()
        if persona_row is not None:
            ai_type_id = int(persona_row.type_id)
            qiao_id = persona_row.qiao_id

    if ai_type_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="请求缺少可识别的 AI 类型，无法恢复待处理",
        )

    normalized_qiao_id = str(qiao_id).strip() if isinstance(qiao_id, str) else ""
    if normalized_qiao_id == "":
        normalized_qiao_id = request_row.to_qiao_id

    return {
        "ai_type_id": ai_type_id,
        "type_id": ai_type_id,
        "qiao_id": normalized_qiao_id,
        "request_id": request_row.id,
    }


async def _build_item_payload(
    db: AsyncSession, request_rows: Sequence[ContactRequest]
) -> list[JSONDict]:
    ai_type_ids: set[str] = set()
    extracted_types: dict[int, str | None] = {}
    now_utc = datetime.now(UTC)

    for row in request_rows:
        detail = row.failure_detail if isinstance(row.failure_detail, dict) else {}
        ai_type_id = _extract_ai_type_id(detail)
        extracted_types[row.id] = ai_type_id
        if ai_type_id is not None:
            ai_type_ids.add(ai_type_id)

    ai_type_name_map = await _load_ai_type_name_map(db, ai_type_ids=ai_type_ids)

    items: list[JSONDict] = []
    for row in request_rows:
        ai_type_id = extracted_types.get(row.id)
        failure = _failure_meta(row.failure_code)
        if int(row.status) == ContactRequestStatus.FAILED and not isinstance(row.failure_code, str):
            failure = FailureCodeMeta(
                label="系统处理异常失败",
                hint="可直接重试；如持续失败请检查后端错误日志",
            )
        item: JSONDict = {
            "request_id": str(row.id),
            "status": int(row.status),
            "from_qiao_id": row.from_qiao_id,
            "to_qiao_id": row.to_qiao_id,
            "from_id": _to_str_id(row.from_id),
            "to_id": _to_str_id(row.to_id),
            "from_type": int(row.from_type),
            "to_type": int(row.to_type),
            "failure_code": row.failure_code,
            "failure_reason_label": failure.label,
            "ai_type_id": ai_type_id,
            "ai_type_display_name": ai_type_name_map.get(ai_type_id, "未知类型")
            if ai_type_id
            else "未知类型",
            "retry_count": int(row.retry_count or 0),
            "is_retryable": _is_retryable_request(
                status_value=int(row.status) if row.status is not None else None,
                failure_code=row.failure_code,
            ),
            "created_at": _to_iso(row.created_at),
            "updated_at": _to_iso(row.updated_at),
            "expires_at": _to_iso(row.expires_at),
            "is_expired": bool(row.expires_at and row.expires_at <= now_utc),
            "last_retry_at": _to_iso(row.last_retry_at),
        }
        items.append(item)
    return items


async def get_incomplete_contact_request_overview(db: AsyncSession) -> JSONDict:
    """Return dashboard overview for incomplete contact requests."""
    incomplete_total_result = await db.execute(
        select(func.count(ContactRequest.id)).where(ContactRequest.status.in_(_INCOMPLETE_STATUSES))
    )
    incomplete_total = int(incomplete_total_result.scalar_one() or 0)

    window_start = datetime.now(UTC) - timedelta(hours=24)
    success_requests_result = await db.execute(
        select(func.count(func.distinct(ContactRequestRetryAttempt.request_id))).where(
            ContactRequestRetryAttempt.result_status
            == ContactRequestRetryResultStatus.SUCCESS.value,
            ContactRequestRetryAttempt.finished_at.is_not(None),
            ContactRequestRetryAttempt.finished_at >= window_start,
        )
    )
    failed_requests_result = await db.execute(
        select(func.count(func.distinct(ContactRequestRetryAttempt.request_id))).where(
            ContactRequestRetryAttempt.result_status.in_(_RETRY_FAILED_STATUSES),
            ContactRequestRetryAttempt.finished_at.is_not(None),
            ContactRequestRetryAttempt.finished_at >= window_start,
        )
    )
    failed_attempts_result = await db.execute(
        select(func.count(ContactRequestRetryAttempt.id)).where(
            ContactRequestRetryAttempt.result_status.in_(_RETRY_FAILED_STATUSES),
            ContactRequestRetryAttempt.finished_at.is_not(None),
            ContactRequestRetryAttempt.finished_at >= window_start,
        )
    )
    blocked_attempts_result = await db.execute(
        select(func.count(ContactRequestRetryAttempt.id)).where(
            ContactRequestRetryAttempt.result_status
            == ContactRequestRetryResultStatus.REJECTED.value,
            ContactRequestRetryAttempt.result_failure_code.not_in(
                (
                    ContactRequestRetryFailureCode.AI_CONTACT_LIMIT_REACHED.value,
                    ContactRequestRetryFailureCode.RETRY_REJECTED.value,
                )
            ),
            ContactRequestRetryAttempt.finished_at.is_not(None),
            ContactRequestRetryAttempt.finished_at >= window_start,
        )
    )

    return {
        "incomplete_total": incomplete_total,
        "last24h_success_requests": int(success_requests_result.scalar_one() or 0),
        "last24h_failed_requests": int(failed_requests_result.scalar_one() or 0),
        "last24h_failed_attempts": int(failed_attempts_result.scalar_one() or 0),
        "last24h_blocked_attempts": int(blocked_attempts_result.scalar_one() or 0),
    }


async def list_incomplete_contact_requests(
    db: AsyncSession,
    *,
    ai_type_id: str | None = None,
    failure_code: str | None = None,
    status: int | None = None,
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> JSONDict:
    """Return paginated incomplete contact request list for admin panel."""
    normalized_limit = normalize_page_limit(limit)
    normalized_offset = max(0, offset)
    normalized_updated_from = normalize_dt_utc(updated_from)
    normalized_updated_to = normalize_dt_utc(updated_to)

    conditions = _base_incomplete_panel_conditions()

    if isinstance(status, int):
        conditions.append(ContactRequest.status == status)
    if isinstance(failure_code, str) and failure_code.strip():
        conditions.append(ContactRequest.failure_code == failure_code.strip())
    if isinstance(ai_type_id, str) and ai_type_id.strip():
        ai_type_value = ai_type_id.strip()
        conditions.append(
            or_(
                ContactRequest.failure_detail["ai_type_id"].astext == ai_type_value,
                ContactRequest.failure_detail["type_id"].astext == ai_type_value,
            )
        )
    if normalized_updated_from is not None:
        conditions.append(ContactRequest.updated_at >= normalized_updated_from)
    if normalized_updated_to is not None:
        conditions.append(ContactRequest.updated_at <= normalized_updated_to)

    total_result = await db.execute(select(func.count(ContactRequest.id)).where(and_(*conditions)))
    total = int(total_result.scalar_one() or 0)

    rows = (
        (
            await db.execute(
                select(ContactRequest)
                .where(and_(*conditions))
                .order_by(ContactRequest.updated_at.desc(), ContactRequest.id.desc())
                .offset(normalized_offset)
                .limit(normalized_limit)
            )
        )
        .scalars()
        .all()
    )

    items = await _build_item_payload(db, rows)
    return {
        "items": cast(JSONValue, items),
        "total": total,
        "limit": normalized_limit,
        "offset": normalized_offset,
    }


async def admin_ignore_incomplete_contact_request(
    db: AsyncSession,
    *,
    request_id: int,
    operator_admin_user_id: int,
    operator_username: str,
    operator_role: int,
) -> JSONDict:
    """Force-ignore an incomplete contact request from admin panel."""
    _assert_admin_can_write(operator_role)
    request_row = await db.get(ContactRequest, request_id, with_for_update=True)
    if request_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="请求不存在")

    if request_row.status == ContactRequestStatus.PROCESSING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前请求正在处理中")
    if request_row.status not in (
        ContactRequestStatus.PENDING,
        ContactRequestStatus.FAILED,
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不允许忽略")

    previous_status = int(request_row.status)
    request_row.status = ContactRequestStatus.IGNORED
    request_row.failure_code = None
    request_row.failure_detail = None
    db.add(request_row)

    await create_operation_log(
        db,
        admin_user_id=operator_admin_user_id,
        operation_type=int(AdminOperationType.UPDATE),
        resource_type="contact_request",
        operation_desc="admin ignore incomplete contact request",
        resource_id=str(request_id),
        resource_name=request_row.to_qiao_id,
        operation_meta={
            "from_status": previous_status,
            "to_status": int(ContactRequestStatus.IGNORED),
            "operator_username": operator_username,
        },
        commit=False,
    )
    await db.commit()

    return {
        "request_id": str(request_row.id),
        "status": int(request_row.status),
    }


async def admin_reopen_ignored_contact_request(
    db: AsyncSession,
    *,
    request_id: int,
    operator_admin_user_id: int,
    operator_username: str,
    operator_role: int,
) -> JSONDict:
    """Reopen an ignored contact request into pending state."""
    _assert_admin_can_write(operator_role)
    request_row = await db.get(ContactRequest, request_id, with_for_update=True)
    if request_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="请求不存在")
    if request_row.status != ContactRequestStatus.IGNORED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="仅已忽略请求可恢复待处理"
        )

    previous_status = int(request_row.status)
    request_row.status = ContactRequestStatus.PENDING
    if request_row.to_type == int(ContactType.AI):
        request_row.failure_code = ContactRequestFailureCode.MANUAL_PROVISION_REQUIRED.value
        request_row.failure_detail = await _build_reopen_failure_detail_for_ai_request(
            db, request_row=request_row
        )
    else:
        request_row.failure_code = None
        request_row.failure_detail = None
    db.add(request_row)

    await create_operation_log(
        db,
        admin_user_id=operator_admin_user_id,
        operation_type=int(AdminOperationType.UPDATE),
        resource_type="contact_request",
        operation_desc="admin reopen ignored contact request to pending",
        resource_id=str(request_id),
        resource_name=request_row.to_qiao_id,
        operation_meta={
            "from_status": previous_status,
            "to_status": int(ContactRequestStatus.PENDING),
            "operator_username": operator_username,
            "expires_at": request_row.expires_at.isoformat() if request_row.expires_at else None,
            "ai_type_id": (
                request_row.failure_detail.get("ai_type_id")
                if isinstance(request_row.failure_detail, dict)
                else None
            ),
        },
        commit=False,
    )
    await db.commit()

    return {
        "request_id": str(request_row.id),
        "status": int(request_row.status),
        "expires_at": _to_iso(request_row.expires_at),
    }

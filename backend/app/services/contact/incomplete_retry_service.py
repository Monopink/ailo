"""Admin incomplete contact request retry service."""

from datetime import UTC, datetime
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.contact import contact_request as contact_request_crud
from app.enums import (
    AdminOperationType,
    AITemplateStatus,
    ContactRequestFailureCode,
    ContactRequestRetryFailureCode,
    ContactRequestRetryMode,
    ContactRequestRetryResultStatus,
    ContactRequestRetryRuleCode,
    ContactRequestStatus,
    ReusableStatus,
)
from app.models.ai.instance import AIInstance
from app.models.ai.personality import AIPersonality
from app.models.ai.style import AIStyle
from app.models.ai.template import AIPersona, AITemplate, AIType
from app.models.contact import ContactRequest, ContactRequestRetryAttempt
from app.services.ai.contact_handler import select_template_for_ai_type
from app.services.contact.ai_contact_request_service import (
    extract_request_tags,
    mark_pending_failure,
    normalize_contact_tags,
    parse_positive_int_or_none,
    process_ai_contact_request,
)
from app.services.entitlement.service import (
    get_ai_contact_limit as get_ai_contact_limit_by_user_id,
)
from app.type_defs import JSONDict, JSONValue
from app.utils.admin_logs import create_operation_log
from app.utils.contact_tags import validate_tags
from app.utils.logging import get_logger

logger = get_logger(__name__)

_RECOVERABLE_PENDING_FAILURE_CODES: set[str] = {
    ContactRequestFailureCode.NO_TEMPLATE_AVAILABLE.value,
    ContactRequestFailureCode.ALL_TEMPLATES_ALREADY_USED.value,
    ContactRequestFailureCode.MANUAL_PROVISION_REQUIRED.value,
}

_PRECHECK_LEVEL_INFO = "INFO"
_PRECHECK_LEVEL_ERROR = "ERROR"
_PRECHECK_LEVEL_HIGH = "HIGH"
_PRECHECK_LEVEL_BLOCKING = "BLOCKING"
_AI_TYPE_SUPPRESSED_REASON_REQUEST_TYPE_MISSING = "REQUEST_AI_TYPE_MISSING_MANUAL_TEMPLATE_RETRY"


def _extract_requested_ai_type_id(contact_request: ContactRequest) -> int | None:
    detail = (
        contact_request.failure_detail if isinstance(contact_request.failure_detail, dict) else {}
    )
    ai_type_raw = detail.get("ai_type_id")
    if ai_type_raw is None:
        ai_type_raw = detail.get("type_id")
    return parse_positive_int_or_none(ai_type_raw)


def _normalize_retry_mode(mode: ContactRequestRetryMode | str | None) -> ContactRequestRetryMode:
    if mode is None:
        return ContactRequestRetryMode.AUTO
    if isinstance(mode, ContactRequestRetryMode):
        return mode
    normalized = mode.strip().upper()
    try:
        return ContactRequestRetryMode(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="重试模式无效") from exc


def _validate_retryable_pending_request(contact_request: ContactRequest | None) -> ContactRequest:
    if contact_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="请求不存在",
        )
    if contact_request.status == ContactRequestStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前请求正在重试处理中",
        )
    if contact_request.status == ContactRequestStatus.FAILED:
        return contact_request
    if contact_request.status != ContactRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只有挂起中或失败的请求可重试",
        )
    if (
        not isinstance(contact_request.failure_code, str)
        or contact_request.failure_code not in _RECOVERABLE_PENDING_FAILURE_CODES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前请求不属于可恢复挂起类型",
        )
    return contact_request


async def _load_retryable_pending_request(
    db: AsyncSession, *, request_id: int, for_update: bool
) -> ContactRequest:
    if for_update:
        loaded_request = await contact_request_crud.get_for_update(db, request_id=request_id)
    else:
        loaded_request = await contact_request_crud.get(db, record_id=request_id)
    return _validate_retryable_pending_request(loaded_request)


async def _load_persona_for_contact_request(
    db: AsyncSession, *, to_qiao_id: str, for_update: bool
) -> AIPersona | None:
    stmt: Select[tuple[AIPersona]] = select(AIPersona).where(AIPersona.qiao_id == to_qiao_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _load_template_for_retry(
    db: AsyncSession, *, template_id: int, for_update: bool
) -> AITemplate | None:
    stmt: Select[tuple[AITemplate]] = select(AITemplate).where(AITemplate.id == template_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _load_ai_type_display_name(db: AsyncSession, *, ai_type_id: int | None) -> str | None:
    if ai_type_id is None:
        return None
    result = await db.execute(select(AIType.display_name).where(AIType.id == ai_type_id))
    display_name = result.scalar_one_or_none()
    return display_name if isinstance(display_name, str) else None


async def _load_ai_type_name_map(db: AsyncSession, *, ai_type_ids: set[int]) -> dict[int, str]:
    if not ai_type_ids:
        return {}
    result = await db.execute(
        select(AIType.id, AIType.display_name).where(AIType.id.in_(ai_type_ids))
    )
    return {int(row.id): str(row.display_name) for row in result}


async def _load_style_name_map(db: AsyncSession, *, style_ids: set[int]) -> dict[int, str]:
    if not style_ids:
        return {}
    result = await db.execute(
        select(AIStyle.id, AIStyle.display_name).where(AIStyle.id.in_(style_ids))
    )
    return {int(row.id): str(row.display_name) for row in result}


async def _load_personality_name_map(
    db: AsyncSession, *, personality_ids: set[int]
) -> dict[int, str]:
    if not personality_ids:
        return {}
    result = await db.execute(
        select(AIPersonality.id, AIPersonality.display_name).where(
            AIPersonality.id.in_(personality_ids)
        )
    )
    return {int(row.id): str(row.display_name) for row in result}


def _template_status_name(status_value: int | None) -> str:
    if status_value is None:
        return "UNKNOWN"
    try:
        return AITemplateStatus(status_value).name
    except ValueError:
        return f"UNKNOWN_{status_value}"


def _build_template_snapshot(
    template: AITemplate | None, *, type_display_name: str | None = None
) -> JSONDict | None:
    if template is None:
        return None
    return {
        "id": str(template.id),
        "display_name": template.display_name or f"Template {template.id}",
        "type_id": str(template.type_id),
        "type_display_name": type_display_name,
        "status": _template_status_name(int(template.status)),
        "is_reusable": bool(int(template.is_reusable) == int(ReusableStatus.REUSABLE)),
        "priority": int(template.priority),
        "style_id": str(template.style_id),
        "personality_id": str(template.personality_id),
        "timezone": template.timezone,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


async def _is_template_used_by_user(db: AsyncSession, *, user_id: int, template_id: int) -> bool:
    result = await db.execute(
        select(AIInstance.id)
        .where(
            AIInstance.user_id == user_id,
            AIInstance.template_id == template_id,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _load_template_availability_counts(
    db: AsyncSession, *, user_id: int, ai_type_id: int | None
) -> tuple[int, int]:
    if ai_type_id is None:
        return 0, 0
    used_template_subquery = select(AIInstance.template_id).where(
        AIInstance.user_id == user_id,
        AIInstance.template_id.is_not(None),
    )
    active_total_result = await db.execute(
        select(func.count(AITemplate.id)).where(
            AITemplate.type_id == ai_type_id,
            AITemplate.status == int(AITemplateStatus.ACTIVE),
        )
    )
    selectable_total_result = await db.execute(
        select(func.count(AITemplate.id)).where(
            AITemplate.type_id == ai_type_id,
            AITemplate.status == int(AITemplateStatus.ACTIVE),
            ~AITemplate.id.in_(used_template_subquery),
        )
    )
    active_total = int(active_total_result.scalar_one() or 0)
    selectable_total = int(selectable_total_result.scalar_one() or 0)
    return active_total, selectable_total


def _build_check(code: ContactRequestRetryRuleCode, *, passed: bool, message: str) -> JSONDict:
    return {
        "code": code.value,
        "level": _PRECHECK_LEVEL_INFO if passed else _PRECHECK_LEVEL_ERROR,
        "passed": passed,
        "message": message,
    }


def _build_warning(code: ContactRequestRetryRuleCode, message: str) -> JSONDict:
    return {"code": code.value, "level": _PRECHECK_LEVEL_HIGH, "message": message}


def _build_blocking_error(code: ContactRequestRetryRuleCode, message: str) -> JSONDict:
    return {"code": code.value, "level": _PRECHECK_LEVEL_BLOCKING, "message": message}


def _build_auto_retry_precheck_payload(
    *,
    requested_ai_type_id: int | None,
    active_total: int,
    selectable_total: int,
) -> tuple[list[JSONDict], list[JSONDict]]:
    checks: list[JSONDict] = []
    warnings: list[JSONDict] = []

    if requested_ai_type_id is None:
        checks.append(
            _build_check(
                ContactRequestRetryRuleCode.REQUEST_AI_TYPE_PRESENT,
                passed=False,
                message="请求缺少可识别的 AI 类型",
            )
        )
        warnings.append(
            _build_warning(
                ContactRequestRetryRuleCode.REQUEST_AI_TYPE_MISSING,
                "请求缺少 AI 类型，自动重试可能失败",
            )
        )
        return checks, warnings

    checks.append(
        _build_check(
            ContactRequestRetryRuleCode.REQUEST_AI_TYPE_PRESENT,
            passed=True,
            message="请求包含 AI 类型信息",
        )
    )

    checks.append(
        _build_check(
            ContactRequestRetryRuleCode.ACTIVE_TEMPLATE_EXISTS,
            passed=active_total > 0,
            message="存在 ACTIVE 模板" if active_total > 0 else "不存在 ACTIVE 模板",
        )
    )
    checks.append(
        _build_check(
            ContactRequestRetryRuleCode.AVAILABLE_TEMPLATE_EXISTS,
            passed=selectable_total > 0,
            message="存在可自动选择模板" if selectable_total > 0 else "不存在可自动选择模板",
        )
    )
    if active_total <= 0:
        warnings.append(
            _build_warning(
                ContactRequestRetryRuleCode.AUTO_NO_ACTIVE_TEMPLATE,
                "当前类型没有 ACTIVE 模板",
            )
        )
    elif selectable_total <= 0:
        warnings.append(
            _build_warning(
                ContactRequestRetryRuleCode.AUTO_NO_SELECTABLE_TEMPLATE,
                "当前用户已用尽该类型可自动选择模板",
            )
        )
    return checks, warnings


async def precheck_incomplete_contact_request_retry(
    db: AsyncSession,
    *,
    request_id: int,
    mode: ContactRequestRetryMode | str,
    selected_ai_type_id: int | None = None,
    selected_template_id: int | None = None,
) -> JSONDict:
    """Build retry precheck report for pending contact request."""
    normalized_mode = _normalize_retry_mode(mode)
    contact_request = await _load_retryable_pending_request(
        db, request_id=request_id, for_update=False
    )

    raw_requested_ai_type_id = _extract_requested_ai_type_id(contact_request)
    requested_ai_type_id = raw_requested_ai_type_id
    if requested_ai_type_id is None:
        persona = await _load_persona_for_contact_request(
            db, to_qiao_id=contact_request.to_qiao_id, for_update=False
        )
        if persona is not None:
            requested_ai_type_id = int(persona.type_id)

    requested_ai_type_name = await _load_ai_type_display_name(
        db, ai_type_id=raw_requested_ai_type_id
    )
    effective_ai_type_id = requested_ai_type_id
    selected_template: AITemplate | None = None
    selected_template_type_name: str | None = None
    if normalized_mode == ContactRequestRetryMode.MANUAL:
        if selected_template_id is None and selected_ai_type_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI type ID is required when selected_template_id is absent",
            )
        if selected_template_id is not None:
            selected_template = await _load_template_for_retry(
                db, template_id=selected_template_id, for_update=False
            )
            if selected_template is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Template not found",
                )
            selected_template_type_name = await _load_ai_type_display_name(
                db, ai_type_id=int(selected_template.type_id)
            )
        if selected_ai_type_id is not None:
            effective_ai_type_id = selected_ai_type_id
        elif selected_template is not None:
            effective_ai_type_id = int(selected_template.type_id)

    effective_ai_type_name = await _load_ai_type_display_name(db, ai_type_id=effective_ai_type_id)
    if normalized_mode == ContactRequestRetryMode.MANUAL and effective_ai_type_name is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI type not found")
    if (
        normalized_mode == ContactRequestRetryMode.MANUAL
        and raw_requested_ai_type_id is None
        and selected_template_id is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request original AI type is missing, selected template is required",
        )

    active_total, selectable_total = await _load_template_availability_counts(
        db,
        user_id=int(contact_request.from_id),
        ai_type_id=effective_ai_type_id,
    )

    checks: list[JSONDict] = [
        _build_check(
            ContactRequestRetryRuleCode.REQUEST_RETRYABLE,
            passed=True,
            message="Request can be retried",
        )
    ]
    blocking_errors: list[JSONDict] = []
    warnings: list[JSONDict] = []

    if normalized_mode == ContactRequestRetryMode.AUTO:
        auto_checks, auto_warnings = _build_auto_retry_precheck_payload(
            requested_ai_type_id=requested_ai_type_id,
            active_total=active_total,
            selectable_total=selectable_total,
        )
        checks.extend(auto_checks)
        warnings.extend(auto_warnings)
    else:
        checks.append(
            _build_check(
                ContactRequestRetryRuleCode.MANUAL_AI_TYPE_PRESENT,
                passed=effective_ai_type_id is not None,
                message=(
                    "Manual retry AI type is selected"
                    if effective_ai_type_id is not None
                    else "Manual retry AI type is missing"
                ),
            )
        )
        manual_checks, manual_warnings = _build_auto_retry_precheck_payload(
            requested_ai_type_id=effective_ai_type_id,
            active_total=active_total,
            selectable_total=selectable_total,
        )
        checks.extend(manual_checks)
        warnings.extend(manual_warnings)

        is_request_type_mismatch = (
            raw_requested_ai_type_id is not None
            and effective_ai_type_id is not None
            and raw_requested_ai_type_id != effective_ai_type_id
        )
        checks.append(
            _build_check(
                ContactRequestRetryRuleCode.MANUAL_AI_TYPE_MATCH_REQUEST,
                passed=not is_request_type_mismatch,
                message=(
                    "Manual retry AI type matches request AI type"
                    if not is_request_type_mismatch
                    else "Manual retry AI type differs from request AI type"
                ),
            )
        )

        if selected_template is not None:
            checks.append(
                _build_check(
                    ContactRequestRetryRuleCode.TEMPLATE_FOUND,
                    passed=True,
                    message="Template exists",
                )
            )
            is_used_by_user = await _is_template_used_by_user(
                db,
                user_id=int(contact_request.from_id),
                template_id=int(selected_template.id),
            )
            checks.append(
                _build_check(
                    ContactRequestRetryRuleCode.TEMPLATE_USED_BY_USER,
                    passed=not is_used_by_user,
                    message=(
                        "Template has not been used by this user yet"
                        if not is_used_by_user
                        else "Template has already been used by this user"
                    ),
                )
            )
            if is_used_by_user:
                blocking_errors.append(
                    _build_blocking_error(
                        ContactRequestRetryRuleCode.TEMPLATE_ALREADY_USED_BY_USER,
                        "Template has already been used by this user",
                    )
                )

            selected_template_type_id = int(selected_template.type_id)
            is_selected_type_mismatch = (
                effective_ai_type_id is not None
                and selected_template_type_id != effective_ai_type_id
            )
            checks.append(
                _build_check(
                    ContactRequestRetryRuleCode.TEMPLATE_TYPE_MATCH_SELECTED_AI_TYPE,
                    passed=not is_selected_type_mismatch,
                    message=(
                        "Template AI type matches selected AI type"
                        if not is_selected_type_mismatch
                        else "Template AI type differs from selected AI type"
                    ),
                )
            )
            if is_selected_type_mismatch:
                warnings.append(
                    _build_warning(
                        ContactRequestRetryRuleCode.TEMPLATE_TYPE_MISMATCH,
                        "Template type does not match selected AI type",
                    )
                )

            template_status = int(selected_template.status)
            is_active = template_status == int(AITemplateStatus.ACTIVE)
            checks.append(
                _build_check(
                    ContactRequestRetryRuleCode.TEMPLATE_STATUS_ACTIVE,
                    passed=is_active,
                    message=(
                        "Template status is ACTIVE"
                        if is_active
                        else "Template status is not ACTIVE"
                    ),
                )
            )
            if not is_active:
                warnings.append(
                    _build_warning(
                        ContactRequestRetryRuleCode.TEMPLATE_STATUS_NON_ACTIVE,
                        f"Template status is {_template_status_name(template_status)}",
                    )
                )

    summary: JSONDict = {
        "blocking_count": len(blocking_errors),
        "warning_count": len(warnings),
        "high_risk_count": len(warnings),
        "can_execute": len(blocking_errors) == 0,
    }
    return {
        "request_id": str(contact_request.id),
        "mode": normalized_mode.value,
        "requested_ai_type_id": str(raw_requested_ai_type_id)
        if raw_requested_ai_type_id is not None
        else None,
        "requested_ai_type_name": requested_ai_type_name,
        "selected_ai_type_id": (
            str(effective_ai_type_id) if effective_ai_type_id is not None else None
        ),
        "selected_ai_type_name": effective_ai_type_name,
        "availability": {
            "active_template_count": active_total,
            "selectable_template_count": selectable_total,
        },
        "selected_template": _build_template_snapshot(
            selected_template, type_display_name=selected_template_type_name
        ),
        "checks": cast(JSONValue, checks),
        "blocking_errors": cast(JSONValue, blocking_errors),
        "warnings": cast(JSONValue, warnings),
        "summary": summary,
    }


def _warnings_from_precheck(precheck_payload: JSONDict) -> list[JSONDict]:
    warnings_raw = precheck_payload.get("warnings")
    if not isinstance(warnings_raw, list):
        return []
    warnings: list[JSONDict] = []
    for item in warnings_raw:
        if isinstance(item, dict):
            warnings.append(item)
    return warnings


def _blocking_errors_from_precheck(precheck_payload: JSONDict) -> list[JSONDict]:
    blocking_errors_raw = precheck_payload.get("blocking_errors")
    if not isinstance(blocking_errors_raw, list):
        return []
    blocking_errors: list[JSONDict] = []
    for item in blocking_errors_raw:
        if isinstance(item, dict):
            blocking_errors.append(item)
    return blocking_errors


async def _resolve_retry_rejected_failure(
    db: AsyncSession,
    *,
    user_id: int,
) -> tuple[str, JSONDict]:
    """Resolve stable failure code/detail for business-level rejected retries."""
    available_total = await get_ai_contact_limit_by_user_id(db, user_id=user_id)
    if available_total <= 0:
        return (
            ContactRequestRetryFailureCode.AI_CONTACT_LIMIT_REACHED.value,
            {"contact_added": False, "available_total": available_total},
        )
    return (
        ContactRequestRetryFailureCode.RETRY_REJECTED.value,
        {"contact_added": False, "reason": "BUSINESS_REJECTED"},
    )


async def _finalize_retry_attempt(
    db: AsyncSession,
    *,
    attempt_id: int,
    result_status: str,
    result_failure_code: str | None,
    result_failure_detail: JSONDict | None,
) -> ContactRequestRetryAttempt | None:
    attempt_row = await db.get(ContactRequestRetryAttempt, attempt_id)
    if attempt_row is None:
        return None
    attempt_row.result_status = result_status
    attempt_row.result_failure_code = result_failure_code
    attempt_row.result_failure_detail = result_failure_detail
    attempt_row.finished_at = datetime.now(UTC)
    db.add(attempt_row)
    await db.commit()
    return attempt_row


async def _restore_request_from_processing(
    db: AsyncSession,
    *,
    request_id: int,
    fallback_failure_code: str | None,
    fallback_failure_detail: JSONDict | None,
) -> None:
    request_row = await contact_request_crud.get_for_update(db, request_id=request_id)
    if request_row is None or request_row.status != ContactRequestStatus.PROCESSING:
        return

    request_row.status = ContactRequestStatus.PENDING
    if isinstance(fallback_failure_code, str) and fallback_failure_code != "":
        request_row.failure_code = fallback_failure_code
    if isinstance(fallback_failure_detail, dict):
        request_row.failure_detail = fallback_failure_detail
    db.add(request_row)
    await db.commit()


def _normalize_precheck_snapshot(precheck_payload: JSONDict | None) -> JSONDict:
    checks: list[JSONValue] = []
    blocking_errors: list[JSONValue] = []
    warnings: list[JSONValue] = []
    summary: JSONDict = {
        "blocking_count": 0,
        "warning_count": 0,
        "high_risk_count": 0,
        "can_execute": True,
    }
    if not isinstance(precheck_payload, dict):
        return {
            "checks": checks,
            "blocking_errors": blocking_errors,
            "warnings": warnings,
            "summary": summary,
        }

    raw_checks = precheck_payload.get("checks")
    if isinstance(raw_checks, list):
        checks = [cast(JSONValue, item) for item in raw_checks if isinstance(item, dict)]

    raw_blocking_errors = precheck_payload.get("blocking_errors")
    if isinstance(raw_blocking_errors, list):
        blocking_errors = [
            cast(JSONValue, item) for item in raw_blocking_errors if isinstance(item, dict)
        ]

    raw_warnings = precheck_payload.get("warnings")
    if isinstance(raw_warnings, list):
        warnings = [cast(JSONValue, item) for item in raw_warnings if isinstance(item, dict)]

    raw_summary = precheck_payload.get("summary")
    if isinstance(raw_summary, dict):
        summary = {str(key): value for key, value in raw_summary.items()}
    else:
        summary = {
            "blocking_count": len(blocking_errors),
            "warning_count": len(warnings),
            "high_risk_count": len(warnings),
            "can_execute": len(blocking_errors) == 0,
        }
    return {
        "checks": checks,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "summary": summary,
    }


async def _next_retry_attempt_no(db: AsyncSession, *, request_id: int) -> int:
    result = await db.execute(
        select(func.max(ContactRequestRetryAttempt.attempt_no)).where(
            ContactRequestRetryAttempt.request_id == request_id
        )
    )
    current_max = result.scalar_one_or_none()
    if isinstance(current_max, int) and current_max > 0:
        return current_max + 1
    return 1


async def _record_blocked_retry_attempt(
    db: AsyncSession,
    *,
    request_id: int,
    mode: ContactRequestRetryMode,
    operator_admin_user_id: int | None,
    operator: str | None,
    selected_ai_type_id: int | None,
    selected_template_id: int | None,
    selected_template_type_id: int | None,
    requested_ai_type_id: int | None,
    is_type_mismatch: bool,
    idempotency_key: str,
    force_continue: bool,
    precheck_snapshot: JSONDict,
    blocking_errors: list[JSONDict],
) -> ContactRequestRetryAttempt:
    attempt_no = await _next_retry_attempt_no(db, request_id=request_id)
    now = datetime.now(UTC)
    result_failure_code = (
        str(blocking_errors[0].get("code"))
        if blocking_errors and isinstance(blocking_errors[0].get("code"), str)
        else ContactRequestRetryRuleCode.TEMPLATE_ALREADY_USED_BY_USER.value
    )
    summary = precheck_snapshot.get("summary")
    precheck_summary: JSONDict = summary if isinstance(summary, dict) else {}
    blocking_errors_json: list[JSONValue] = [cast(JSONValue, item) for item in blocking_errors]
    precheck_summary = {
        **precheck_summary,
        "blocking_count": len(blocking_errors),
        "warning_count": precheck_summary.get("warning_count", 0),
        "high_risk_count": precheck_summary.get("high_risk_count", 0),
        "can_execute": False,
        "blocking_errors": blocking_errors_json,
    }
    attempt = ContactRequestRetryAttempt(
        request_id=request_id,
        attempt_no=attempt_no,
        operator_admin_user_id=operator_admin_user_id,
        operator_username=operator,
        mode=mode.value,
        selected_ai_type_id=selected_ai_type_id,
        selected_template_id=selected_template_id,
        force_continue=force_continue,
        idempotency_key=idempotency_key,
        precheck_checks=precheck_snapshot.get("checks", []),
        precheck_warnings=precheck_snapshot.get("warnings", []),
        precheck_summary=precheck_summary,
        requested_ai_type_id=requested_ai_type_id,
        selected_template_type_id=selected_template_type_id,
        is_type_mismatch=is_type_mismatch,
        result_status=ContactRequestRetryResultStatus.REJECTED.value,
        result_failure_code=result_failure_code,
        result_failure_detail={"blocking_errors": blocking_errors},
        started_at=now,
        finished_at=now,
    )
    db.add(attempt)
    await db.commit()
    return attempt


def _build_retry_execution_response(
    *,
    request_id: int,
    attempt_row: ContactRequestRetryAttempt | None,
    refreshed_request: ContactRequest | None,
    is_idempotent_replay: bool,
) -> JSONDict:
    request_status_after: int | None = (
        int(refreshed_request.status) if refreshed_request is not None else None
    )
    retry_count_after: int | None = (
        int(refreshed_request.retry_count or 0) if refreshed_request is not None else None
    )
    last_retry_at = (
        refreshed_request.last_retry_at.isoformat()
        if refreshed_request is not None and refreshed_request.last_retry_at is not None
        else None
    )
    if attempt_row is None:
        return {
            "attempt_id": None,
            "request_id": str(request_id),
            "result_status": ContactRequestRetryResultStatus.ERROR.value,
            "result_failure_code": ContactRequestRetryFailureCode.RETRY_ATTEMPT_NOT_FOUND.value,
            "result_failure_detail": {"message": "未找到重试记录"},
            "request_status_after": request_status_after,
            "retry_count_after": retry_count_after,
            "last_retry_at": last_retry_at,
            "is_idempotent_replay": is_idempotent_replay,
        }

    return {
        "attempt_id": str(attempt_row.id),
        "request_id": str(request_id),
        "result_status": attempt_row.result_status,
        "result_failure_code": attempt_row.result_failure_code,
        "result_failure_detail": attempt_row.result_failure_detail,
        "request_status_after": request_status_after,
        "retry_count_after": retry_count_after,
        "last_retry_at": last_retry_at,
        "is_idempotent_replay": is_idempotent_replay,
    }


def parse_template_id_or_400(raw_template_id: str) -> int:
    candidate = raw_template_id.strip()
    if not candidate.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid template id")
    template_id = int(candidate)
    if template_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid template id")
    return template_id


def parse_ai_type_id_or_400(raw_ai_type_id: str) -> int:
    candidate = raw_ai_type_id.strip()
    if not candidate.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid AI type id")
    ai_type_id = int(candidate)
    if ai_type_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid AI type id")
    return ai_type_id


async def search_ai_types_for_retry(
    db: AsyncSession,
    *,
    query: str,
    limit: int,
    page: int,
) -> JSONDict:
    normalized_query = query.strip()
    offset = max(page - 1, 0) * limit

    stmt: Select[tuple[AIType]] = (
        select(AIType)
        .order_by(AIType.updated_at.desc(), AIType.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )

    if normalized_query != "":
        if normalized_query.isdigit():
            ai_type_id = int(normalized_query)
            stmt = stmt.where(
                or_(
                    AIType.id == ai_type_id,
                    AIType.display_name.ilike(f"%{normalized_query}%"),
                )
            )
        else:
            stmt = stmt.where(AIType.display_name.ilike(f"%{normalized_query}%"))

    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items: list[JSONDict] = []
    for row in rows:
        items.append(
            {
                "id": str(row.id),
                "text": f"[{row.id}] {row.display_name}",
                "meta": {
                    "ai_type_id": str(row.id),
                    "ai_type_display_name": row.display_name,
                    "description": row.description,
                },
            }
        )
    return {"items": cast(JSONValue, items), "has_more": has_more}


async def search_templates_for_retry(
    db: AsyncSession,
    *,
    query: str,
    limit: int,
    page: int,
    ai_type_id: int | None = None,
) -> JSONDict:
    normalized_query = query.strip()
    if normalized_query == "" and ai_type_id is None:
        return {"items": [], "has_more": False}

    offset = max(page - 1, 0) * limit
    stmt: Select[tuple[AITemplate]] = (
        select(AITemplate)
        .order_by(AITemplate.updated_at.desc(), AITemplate.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    if ai_type_id is not None:
        stmt = stmt.where(AITemplate.type_id == ai_type_id)

    if normalized_query != "":
        if normalized_query.isdigit():
            template_id = int(normalized_query)
            stmt = stmt.where(
                or_(
                    AITemplate.id == template_id,
                    AITemplate.display_name.ilike(f"%{normalized_query}%"),
                )
            )
        else:
            stmt = stmt.where(AITemplate.display_name.ilike(f"%{normalized_query}%"))

    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    ai_type_name_map = await _load_ai_type_name_map(
        db,
        ai_type_ids={int(row.type_id) for row in rows},
    )
    style_name_map = await _load_style_name_map(
        db,
        style_ids={int(row.style_id) for row in rows},
    )
    personality_name_map = await _load_personality_name_map(
        db,
        personality_ids={int(row.personality_id) for row in rows},
    )
    items: list[JSONDict] = []
    for row in rows:
        status_name = _template_status_name(int(row.status))
        type_name = ai_type_name_map.get(int(row.type_id), "Unknown")
        display_name = row.display_name or f"Template {row.id}"
        priority = int(row.priority)
        item: JSONDict = {
            "id": str(row.id),
            "text": f"[{row.id}] {display_name} ({status_name}, P={priority})",
            "meta": {
                "template_id": str(row.id),
                "display_name": display_name,
                "type_id": str(row.type_id),
                "type_display_name": type_name,
                "status": status_name,
                "is_reusable": bool(int(row.is_reusable) == int(ReusableStatus.REUSABLE)),
                "priority": priority,
                "style_id": str(row.style_id),
                "style_display_name": style_name_map.get(int(row.style_id)),
                "personality_id": str(row.personality_id),
                "personality_display_name": personality_name_map.get(int(row.personality_id)),
                "timezone": row.timezone,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            },
        }
        items.append(item)
    return {"items": cast(JSONValue, items), "has_more": has_more}


async def _load_requested_ai_type_id_for_retry(
    db: AsyncSession,
    *,
    contact_request: ContactRequest,
) -> tuple[int | None, int | None]:
    raw_requested_ai_type_id = _extract_requested_ai_type_id(contact_request)
    requested_ai_type_id = raw_requested_ai_type_id
    if requested_ai_type_id is None:
        persona = await _load_persona_for_contact_request(
            db, to_qiao_id=contact_request.to_qiao_id, for_update=True
        )
        if persona is not None:
            requested_ai_type_id = int(persona.type_id)
    return raw_requested_ai_type_id, requested_ai_type_id


async def _resolve_retry_template_selection(
    db: AsyncSession,
    *,
    contact_request: ContactRequest,
    normalized_mode: ContactRequestRetryMode,
    raw_requested_ai_type_id: int | None,
    requested_ai_type_id: int | None,
    selected_ai_type_id: int | None,
    selected_template_id: int | None,
) -> tuple[int | None, AITemplate | None, int | None, int | None, str | None, bool]:
    effective_selected_ai_type_id = requested_ai_type_id
    selected_template: AITemplate | None = None
    selected_template_type_id: int | None = None
    template_selection_failure_code: str | None = None
    resolved_template_id = selected_template_id

    if normalized_mode == ContactRequestRetryMode.MANUAL:
        if resolved_template_id is None and selected_ai_type_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI type ID is required when selected_template_id is absent",
            )

        if resolved_template_id is not None:
            selected_template = await _load_template_for_retry(
                db, template_id=resolved_template_id, for_update=True
            )
            if selected_template is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Template not found",
                )
            selected_template_type_id = int(selected_template.type_id)

        if selected_ai_type_id is not None:
            if await _load_ai_type_display_name(db, ai_type_id=selected_ai_type_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="AI type not found",
                )
            effective_selected_ai_type_id = selected_ai_type_id
        elif selected_template_type_id is not None:
            effective_selected_ai_type_id = selected_template_type_id

        if selected_template is None:
            if raw_requested_ai_type_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Request original AI type is missing, selected template is required",
                )
            if effective_selected_ai_type_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="AI type cannot be resolved for manual retry",
                )
            selected_template, template_selection_failure_code = await select_template_for_ai_type(
                db,
                type_id=effective_selected_ai_type_id,
                user_id=int(contact_request.from_id),
            )
            if selected_template is not None:
                resolved_template_id = int(selected_template.id)
                selected_template_type_id = int(selected_template.type_id)

    is_type_mismatch = (
        raw_requested_ai_type_id is not None
        and selected_template_type_id is not None
        and raw_requested_ai_type_id != selected_template_type_id
    )
    return (
        effective_selected_ai_type_id,
        selected_template,
        resolved_template_id,
        selected_template_type_id,
        template_selection_failure_code,
        is_type_mismatch,
    )


def _build_runtime_precheck_snapshot(
    *,
    runtime_precheck_report: JSONDict,
    precheck_payload: JSONDict | None,
) -> tuple[JSONDict, list[JSONDict], list[JSONDict]]:
    runtime_precheck_snapshot = _normalize_precheck_snapshot(runtime_precheck_report)
    client_precheck_snapshot = _normalize_precheck_snapshot(precheck_payload)
    runtime_precheck_summary = runtime_precheck_snapshot.get("summary")
    if isinstance(runtime_precheck_summary, dict):
        runtime_precheck_summary["client_precheck_snapshot"] = client_precheck_snapshot
        runtime_precheck_snapshot["summary"] = runtime_precheck_summary
    runtime_warnings = _warnings_from_precheck(runtime_precheck_snapshot)
    runtime_blocking_errors = _blocking_errors_from_precheck(runtime_precheck_snapshot)
    return runtime_precheck_snapshot, runtime_warnings, runtime_blocking_errors


async def _raise_for_blocking_precheck(
    db: AsyncSession,
    *,
    request_id: int,
    normalized_mode: ContactRequestRetryMode,
    operator_admin_user_id: int | None,
    operator: str | None,
    contact_request: ContactRequest,
    effective_selected_ai_type_id: int | None,
    selected_template_id: int | None,
    selected_template_type_id: int | None,
    raw_requested_ai_type_id: int | None,
    is_type_mismatch: bool,
    normalized_idempotency_key: str,
    force_continue: bool,
    runtime_precheck_snapshot: JSONDict,
    runtime_warnings: list[JSONDict],
    runtime_blocking_errors: list[JSONDict],
) -> None:
    blocked_attempt = await _record_blocked_retry_attempt(
        db,
        request_id=request_id,
        mode=normalized_mode,
        operator_admin_user_id=operator_admin_user_id,
        operator=operator,
        selected_ai_type_id=effective_selected_ai_type_id,
        selected_template_id=selected_template_id,
        selected_template_type_id=selected_template_type_id,
        requested_ai_type_id=raw_requested_ai_type_id,
        is_type_mismatch=is_type_mismatch,
        idempotency_key=normalized_idempotency_key,
        force_continue=force_continue,
        precheck_snapshot=runtime_precheck_snapshot,
        blocking_errors=runtime_blocking_errors,
    )
    first_blocking_error = runtime_blocking_errors[0]
    if operator_admin_user_id is not None and operator:
        await create_operation_log(
            db,
            admin_user_id=operator_admin_user_id,
            operation_type=int(AdminOperationType.EXECUTE),
            resource_type="contact_request_retry",
            operation_desc="admin retry incomplete contact request blocked",
            resource_id=str(request_id),
            resource_name=contact_request.to_qiao_id,
            operation_meta={
                "mode": normalized_mode.value,
                "selected_ai_type_id": (
                    str(effective_selected_ai_type_id)
                    if effective_selected_ai_type_id is not None
                    else None
                ),
                "selected_template_id": (
                    str(selected_template_id) if selected_template_id is not None else None
                ),
                "force_continue": force_continue,
                "idempotency_key": normalized_idempotency_key,
                "warning_count": len(runtime_warnings),
                "blocking_count": len(runtime_blocking_errors),
                "result_status": blocked_attempt.result_status,
                "result_failure_code": blocked_attempt.result_failure_code,
            },
        )
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=first_blocking_error)


def _resolve_retry_execution_overrides(
    *,
    contact_request: ContactRequest,
    alias: str | None,
    tags: list[str] | None,
) -> tuple[str | None, list[str] | None]:
    normalized_override_tags = normalize_contact_tags(tags) if tags is not None else None
    if normalized_override_tags is not None:
        tag_error = validate_tags(normalized_override_tags)
        if tag_error is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=tag_error,
            )
    effective_alias = alias if alias is not None else contact_request.alias
    extracted_stored_tags = extract_request_tags(contact_request.tags)
    if tags is None and contact_request.tags is not None and extracted_stored_tags is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "CONTACT_PRESET_INVALID"},
        )
    effective_tags = normalized_override_tags if tags is not None else extracted_stored_tags
    return effective_alias, effective_tags


def _build_fallback_failure_state(
    *,
    contact_request: ContactRequest,
) -> tuple[str, JSONDict]:
    fallback_failure_detail = (
        contact_request.failure_detail if isinstance(contact_request.failure_detail, dict) else {}
    )
    fallback_failure_code = contact_request.failure_code
    if not isinstance(fallback_failure_code, str) or fallback_failure_code == "":
        fallback_failure_code = ContactRequestFailureCode.MANUAL_PROVISION_REQUIRED.value
    return fallback_failure_code, fallback_failure_detail


async def _create_processing_retry_attempt(
    db: AsyncSession,
    *,
    request_id: int,
    contact_request: ContactRequest,
    normalized_mode: ContactRequestRetryMode,
    selected_ai_type_id: int | None,
    selected_template_id: int | None,
    selected_template_type_id: int | None,
    force_continue: bool,
    normalized_idempotency_key: str,
    runtime_precheck_snapshot: JSONDict,
    raw_requested_ai_type_id: int | None,
    is_type_mismatch: bool,
    operator_admin_user_id: int | None,
    operator: str | None,
) -> int:
    attempt_no = await _next_retry_attempt_no(db, request_id=request_id)
    started_at = datetime.now(UTC)
    attempt = ContactRequestRetryAttempt(
        request_id=request_id,
        attempt_no=attempt_no,
        operator_admin_user_id=operator_admin_user_id,
        operator_username=operator,
        mode=normalized_mode.value,
        selected_ai_type_id=selected_ai_type_id,
        selected_template_id=selected_template_id,
        force_continue=force_continue,
        idempotency_key=normalized_idempotency_key,
        precheck_checks=runtime_precheck_snapshot.get("checks", []),
        precheck_warnings=runtime_precheck_snapshot.get("warnings", []),
        precheck_summary=runtime_precheck_snapshot.get("summary", {}),
        requested_ai_type_id=raw_requested_ai_type_id,
        selected_template_type_id=selected_template_type_id,
        is_type_mismatch=is_type_mismatch,
        result_status=ContactRequestRetryResultStatus.FAILED.value,
        started_at=started_at,
    )
    db.add(attempt)
    contact_request.status = ContactRequestStatus.PROCESSING
    contact_request.retry_count = (contact_request.retry_count or 0) + 1
    contact_request.last_retry_at = started_at
    db.add(contact_request)
    await db.flush()
    attempt_id_raw = getattr(attempt, "id", None)
    if not isinstance(attempt_id_raw, int) or attempt_id_raw <= 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System error",
        )
    await db.commit()
    return attempt_id_raw


async def _execute_retry_processing_flow(
    db: AsyncSession,
    *,
    request_id: int,
    contact_request: ContactRequest,
    normalized_mode: ContactRequestRetryMode,
    selected_template: AITemplate | None,
    selected_template_id: int | None,
    template_selection_failure_code: str | None,
    effective_selected_ai_type_id: int | None,
    raw_requested_ai_type_id: int | None,
    effective_alias: str | None,
    effective_tags: list[str] | None,
    fallback_failure_code: str,
    fallback_failure_detail: JSONDict,
) -> tuple[str, str | None, JSONDict | None, ContactRequest | None, int | None]:
    result_status = ContactRequestRetryResultStatus.FAILED.value
    result_failure_code: str | None = None
    result_failure_detail: JSONDict | None = None
    resulting_status_value: int | None = None

    if normalized_mode == ContactRequestRetryMode.MANUAL and selected_template is None:
        failure_code = (
            template_selection_failure_code or ContactRequestFailureCode.NO_TEMPLATE_AVAILABLE.value
        )
        mark_pending_failure(
            contact_request,
            persona=None,
            reason=failure_code,
            ai_type_id_override=effective_selected_ai_type_id,
        )
        db.add(contact_request)
        result_failure_code = failure_code
        result_failure_detail = {
            "message": "No selectable template for selected AI type",
            "selected_ai_type_id": effective_selected_ai_type_id,
        }
        await db.commit()
    else:
        selected_template_for_execution = selected_template
        if selected_template_for_execution is not None:
            if selected_template_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Template id is required for execution",
                )
            selected_template_for_execution = await _load_template_for_retry(
                db,
                template_id=int(selected_template_id),
                for_update=True,
            )
            if selected_template_for_execution is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Template not found",
                )
            if await _is_template_used_by_user(
                db,
                user_id=int(contact_request.from_id),
                template_id=int(selected_template_for_execution.id),
            ):
                blocking_error = _build_blocking_error(
                    ContactRequestRetryRuleCode.TEMPLATE_ALREADY_USED_BY_USER,
                    "Template has already been used by this user",
                )
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=blocking_error)

        await process_ai_contact_request(
            db=db,
            user_qiao_id=contact_request.from_qiao_id,
            user_id=contact_request.from_id,
            contact_request=contact_request,
            alias=effective_alias,
            tags=effective_tags,
            selected_template_override=selected_template_for_execution,
            suppress_instance_ai_type=(
                normalized_mode == ContactRequestRetryMode.MANUAL
                and raw_requested_ai_type_id is None
                and selected_template_for_execution is not None
            ),
            ai_type_suppressed_reason=(
                _AI_TYPE_SUPPRESSED_REASON_REQUEST_TYPE_MISSING
                if (
                    normalized_mode == ContactRequestRetryMode.MANUAL
                    and raw_requested_ai_type_id is None
                    and selected_template_for_execution is not None
                )
                else None
            ),
            mark_failed_on_unexpected_error=False,
        )

    refreshed_request = await contact_request_crud.get(db, record_id=request_id)
    if (
        refreshed_request is not None
        and refreshed_request.status == ContactRequestStatus.PROCESSING
    ):
        await _restore_request_from_processing(
            db,
            request_id=request_id,
            fallback_failure_code=fallback_failure_code,
            fallback_failure_detail=fallback_failure_detail,
        )
        refreshed_request = await contact_request_crud.get(db, record_id=request_id)

    if refreshed_request is not None:
        resulting_status_value = int(refreshed_request.status)
        if refreshed_request.status == ContactRequestStatus.ACCEPTED:
            result_status = ContactRequestRetryResultStatus.SUCCESS.value
        elif refreshed_request.status == ContactRequestStatus.IGNORED:
            result_status = ContactRequestRetryResultStatus.REJECTED.value
            if result_failure_code is None:
                (
                    result_failure_code,
                    resolved_failure_detail,
                ) = await _resolve_retry_rejected_failure(
                    db,
                    user_id=int(contact_request.from_id),
                )
                if result_failure_detail is None:
                    result_failure_detail = resolved_failure_detail
        else:
            result_status = ContactRequestRetryResultStatus.FAILED.value

        if result_failure_code is None and isinstance(refreshed_request.failure_code, str):
            result_failure_code = refreshed_request.failure_code
        if result_failure_detail is None and isinstance(refreshed_request.failure_detail, dict):
            result_failure_detail = refreshed_request.failure_detail

    return (
        result_status,
        result_failure_code,
        result_failure_detail,
        refreshed_request,
        resulting_status_value,
    )


async def retry_incomplete_contact_request(
    db: AsyncSession,
    *,
    request_id: int,
    mode: ContactRequestRetryMode | str = ContactRequestRetryMode.AUTO,
    selected_ai_type_id: int | None = None,
    selected_template_id: int | None = None,
    force_continue: bool = False,
    idempotency_key: str,
    alias: str | None = None,
    tags: list[str] | None = None,
    operator_admin_user_id: int | None = None,
    operator: str | None = None,
    precheck_payload: JSONDict | None = None,
) -> JSONDict:
    """Retry an incomplete AI contact request with AUTO or MANUAL mode."""
    normalized_mode = _normalize_retry_mode(mode)
    normalized_idempotency_key = idempotency_key.strip()
    if normalized_idempotency_key == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency key is required",
        )
    refreshed_request: ContactRequest | None = None

    duplicate_attempt_result = await db.execute(
        select(ContactRequestRetryAttempt).where(
            ContactRequestRetryAttempt.request_id == request_id,
            ContactRequestRetryAttempt.idempotency_key == normalized_idempotency_key,
        )
    )
    duplicate_attempt = duplicate_attempt_result.scalar_one_or_none()
    if duplicate_attempt is not None:
        refreshed_request = await contact_request_crud.get(db, record_id=request_id)
        return _build_retry_execution_response(
            request_id=request_id,
            attempt_row=duplicate_attempt,
            refreshed_request=refreshed_request,
            is_idempotent_replay=True,
        )

    contact_request = await _load_retryable_pending_request(
        db, request_id=request_id, for_update=True
    )
    raw_requested_ai_type_id, requested_ai_type_id = await _load_requested_ai_type_id_for_retry(
        db,
        contact_request=contact_request,
    )
    (
        effective_selected_ai_type_id,
        selected_template,
        selected_template_id,
        selected_template_type_id,
        template_selection_failure_code,
        is_type_mismatch,
    ) = await _resolve_retry_template_selection(
        db,
        contact_request=contact_request,
        normalized_mode=normalized_mode,
        raw_requested_ai_type_id=raw_requested_ai_type_id,
        requested_ai_type_id=requested_ai_type_id,
        selected_ai_type_id=selected_ai_type_id,
        selected_template_id=selected_template_id,
    )

    runtime_precheck_report = await precheck_incomplete_contact_request_retry(
        db,
        request_id=request_id,
        mode=normalized_mode,
        selected_ai_type_id=(
            effective_selected_ai_type_id
            if normalized_mode == ContactRequestRetryMode.MANUAL
            else None
        ),
        selected_template_id=selected_template_id,
    )
    (
        runtime_precheck_snapshot,
        runtime_warnings,
        runtime_blocking_errors,
    ) = _build_runtime_precheck_snapshot(
        runtime_precheck_report=runtime_precheck_report,
        precheck_payload=precheck_payload,
    )
    if runtime_blocking_errors:
        await _raise_for_blocking_precheck(
            db,
            request_id=request_id,
            normalized_mode=normalized_mode,
            operator_admin_user_id=operator_admin_user_id,
            operator=operator,
            contact_request=contact_request,
            effective_selected_ai_type_id=effective_selected_ai_type_id,
            selected_template_id=selected_template_id,
            selected_template_type_id=selected_template_type_id,
            raw_requested_ai_type_id=raw_requested_ai_type_id,
            is_type_mismatch=is_type_mismatch,
            normalized_idempotency_key=normalized_idempotency_key,
            force_continue=force_continue,
            runtime_precheck_snapshot=runtime_precheck_snapshot,
            runtime_warnings=runtime_warnings,
            runtime_blocking_errors=runtime_blocking_errors,
        )
    if runtime_warnings and not force_continue:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Precheck has risk warnings, please confirm force continue",
        )

    effective_alias, effective_tags = _resolve_retry_execution_overrides(
        contact_request=contact_request,
        alias=alias,
        tags=tags,
    )
    fallback_failure_code, fallback_failure_detail = _build_fallback_failure_state(
        contact_request=contact_request,
    )
    attempt_id = await _create_processing_retry_attempt(
        db,
        request_id=request_id,
        contact_request=contact_request,
        normalized_mode=normalized_mode,
        selected_ai_type_id=effective_selected_ai_type_id,
        selected_template_id=selected_template_id,
        selected_template_type_id=selected_template_type_id,
        force_continue=force_continue,
        normalized_idempotency_key=normalized_idempotency_key,
        runtime_precheck_snapshot=runtime_precheck_snapshot,
        raw_requested_ai_type_id=raw_requested_ai_type_id,
        is_type_mismatch=is_type_mismatch,
        operator_admin_user_id=operator_admin_user_id,
        operator=operator,
    )

    result_status = ContactRequestRetryResultStatus.FAILED.value
    result_failure_code: str | None = None
    final_attempt_row: ContactRequestRetryAttempt | None = None
    resulting_status_value: int | None = None
    try:
        (
            result_status,
            result_failure_code,
            result_failure_detail,
            refreshed_request,
            resulting_status_value,
        ) = await _execute_retry_processing_flow(
            db,
            request_id=request_id,
            contact_request=contact_request,
            normalized_mode=normalized_mode,
            selected_template=selected_template,
            selected_template_id=selected_template_id,
            template_selection_failure_code=template_selection_failure_code,
            effective_selected_ai_type_id=effective_selected_ai_type_id,
            raw_requested_ai_type_id=raw_requested_ai_type_id,
            effective_alias=effective_alias,
            effective_tags=effective_tags,
            fallback_failure_code=fallback_failure_code,
            fallback_failure_detail=fallback_failure_detail,
        )
        final_attempt_row = await _finalize_retry_attempt(
            db,
            attempt_id=attempt_id,
            result_status=result_status,
            result_failure_code=result_failure_code,
            result_failure_detail=result_failure_detail,
        )
    except HTTPException as exc:
        await db.rollback()
        await _restore_request_from_processing(
            db,
            request_id=request_id,
            fallback_failure_code=fallback_failure_code,
            fallback_failure_detail=fallback_failure_detail,
        )
        http_failure_code = ContactRequestRetryFailureCode.RETRY_REJECTED.value
        exc_detail_obj: object = exc.detail
        if exc.status_code == status.HTTP_409_CONFLICT and isinstance(exc_detail_obj, dict):
            blocking_code = exc_detail_obj.get("code")
            if isinstance(blocking_code, str) and blocking_code != "":
                http_failure_code = blocking_code
        final_attempt_row = await _finalize_retry_attempt(
            db,
            attempt_id=attempt_id,
            result_status=ContactRequestRetryResultStatus.REJECTED.value,
            result_failure_code=http_failure_code,
            result_failure_detail={"detail": exc.detail},
        )
        raise
    except IntegrityError as exc:
        await db.rollback()
        await _restore_request_from_processing(
            db,
            request_id=request_id,
            fallback_failure_code=fallback_failure_code,
            fallback_failure_detail=fallback_failure_detail,
        )
        error_text = str(getattr(exc, "orig", exc))
        is_template_reuse_integrity_error = "uq_ai_instances_user_template" in error_text
        if is_template_reuse_integrity_error:
            blocking_error = _build_blocking_error(
                ContactRequestRetryRuleCode.TEMPLATE_ALREADY_USED_BY_USER,
                "Template has already been used by this user",
            )
            final_attempt_row = await _finalize_retry_attempt(
                db,
                attempt_id=attempt_id,
                result_status=ContactRequestRetryResultStatus.REJECTED.value,
                result_failure_code=ContactRequestRetryRuleCode.TEMPLATE_ALREADY_USED_BY_USER.value,
                result_failure_detail={"detail": blocking_error},
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=blocking_error,
            ) from exc
        final_attempt_row = await _finalize_retry_attempt(
            db,
            attempt_id=attempt_id,
            result_status=ContactRequestRetryResultStatus.ERROR.value,
            result_failure_code=ContactRequestRetryFailureCode.RETRY_EXCEPTION.value,
            result_failure_detail={"error": error_text},
        )
        logger.error(
            "contact_request_retry_failed",
            request_id=request_id,
            error=error_text,
            operator=operator or "system",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System error",
        ) from exc
    except Exception as exc:
        await db.rollback()
        await _restore_request_from_processing(
            db,
            request_id=request_id,
            fallback_failure_code=fallback_failure_code,
            fallback_failure_detail=fallback_failure_detail,
        )
        final_attempt_row = await _finalize_retry_attempt(
            db,
            attempt_id=attempt_id,
            result_status=ContactRequestRetryResultStatus.ERROR.value,
            result_failure_code=ContactRequestRetryFailureCode.RETRY_EXCEPTION.value,
            result_failure_detail={"error": str(exc)},
        )
        logger.error(
            "contact_request_retry_failed",
            request_id=request_id,
            error=str(exc),
            operator=operator or "system",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System error",
        ) from exc

    if operator_admin_user_id is not None and operator:
        await create_operation_log(
            db,
            admin_user_id=operator_admin_user_id,
            operation_type=int(AdminOperationType.EXECUTE),
            resource_type="contact_request_retry",
            operation_desc="admin retry incomplete contact request",
            resource_id=str(request_id),
            resource_name=contact_request.to_qiao_id,
            operation_meta={
                "mode": normalized_mode.value,
                "selected_ai_type_id": (
                    str(effective_selected_ai_type_id)
                    if effective_selected_ai_type_id is not None
                    else None
                ),
                "selected_template_id": (
                    str(selected_template_id) if selected_template_id is not None else None
                ),
                "force_continue": force_continue,
                "idempotency_key": normalized_idempotency_key,
                "warning_count": len(runtime_warnings),
                "result_status": result_status,
                "result_failure_code": result_failure_code,
            },
        )

    logger.info(
        "contact_request_retry",
        request_id=request_id,
        from_qiao_id=contact_request.from_qiao_id,
        to_qiao_id=contact_request.to_qiao_id,
        retry_count=contact_request.retry_count,
        resulting_status=resulting_status_value,
        operator=operator or "system",
        mode=normalized_mode.value,
        force_continue=force_continue,
    )
    if refreshed_request is None:
        refreshed_request = await contact_request_crud.get(db, record_id=request_id)
    if final_attempt_row is None:
        final_attempt_row = await db.get(ContactRequestRetryAttempt, attempt_id)
    return _build_retry_execution_response(
        request_id=request_id,
        attempt_row=final_attempt_row,
        refreshed_request=refreshed_request,
        is_idempotent_replay=False,
    )


# Background processing moved to services.contact.request_worker

"""Shared AI contact request processing helpers and flow."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.contact import contact as contact_crud
from app.crud.contact import contact_request as contact_request_crud
from app.enums import (
    CHAT_INFO_TEMPLATES,
    ChatInfoType,
    ContactRequestFailureCode,
    ContactRequestSource,
    ContactRequestStatus,
    ContactSource,
    ContactType,
)
from app.models.ai.template import AIPersona, AITemplate
from app.models.contact import Contact, ContactRequest
from app.models.content import SquareCategory
from app.models.user import User
from app.schemas.contact import ContactCreate
from app.services.ai.contact_handler import ContactRequestDecision, handle_ai_contact_request
from app.services.ai.instance_creation import create_instance_from_persona
from app.services.entitlement.service import (
    ENTITLEMENT_AI_CONTACT_LIMIT,
    ENTITLEMENT_SOURCE_CONTACT_AI_SLOT,
    consume_entitlement,
)
from app.services.entitlement.service import (
    get_ai_contact_limit as get_ai_contact_limit_by_user_id,
)
from app.services.message.outbound.helpers import send_chat_info
from app.type_defs import JSONDict, JSONValue
from app.utils.contact_tags import normalize_tags, validate_tags
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id
from app.utils.text_limits import CONTACT_REMARK_RULE, validate_text_limit

logger = get_logger(__name__)


def parse_positive_int_or_none(raw_value: object) -> int | None:
    """Parse positive integer value from int/decimal string input."""
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


def extract_request_tags(tags_payload: JSONValue | None) -> list[str] | None:
    """Extract contact tags from request payload representation."""
    if tags_payload is None:
        return None
    if isinstance(tags_payload, list):
        return [item for item in tags_payload if isinstance(item, str)]
    if isinstance(tags_payload, dict):
        raw_tags = tags_payload.get("tags")
        if isinstance(raw_tags, list):
            return [item for item in raw_tags if isinstance(item, str)]
    return None


def normalize_contact_tags(raw_tags: list[str] | None) -> list[str] | None:
    """Normalize contact tags with shared utility."""
    return normalize_tags(raw_tags)


def mark_pending_failure(
    contact_request: ContactRequest,
    *,
    persona: AIPersona | None,
    reason: str,
    ai_type_id_override: int | None = None,
) -> None:
    """Record pending failure metadata and update request state."""
    existing_detail = contact_request.failure_detail or {}
    ai_type_raw: object = ai_type_id_override
    if ai_type_raw is None:
        ai_type_raw = (
            persona.type_id
            if persona
            else (existing_detail.get("ai_type_id") or existing_detail.get("type_id"))
        )
    ai_type_id = parse_positive_int_or_none(ai_type_raw)
    qiao_id = persona.qiao_id if persona else existing_detail.get("qiao_id")
    detail = {
        "ai_type_id": ai_type_id,
        "type_id": ai_type_id,
        "qiao_id": qiao_id,
        "request_id": contact_request.id,
    }
    contact_request.status = ContactRequestStatus.PENDING
    contact_request.failure_code = reason
    contact_request.failure_detail = detail
    logger.info(
        "contact_request_pending",
        request_id=contact_request.id,
        from_qiao_id=contact_request.from_qiao_id,
        to_qiao_id=contact_request.to_qiao_id,
        ai_type_id=ai_type_id,
        failure_code=reason,
    )


def clear_pending_failure(contact_request: ContactRequest) -> None:
    """Clear pending failure metadata from request state."""
    contact_request.failure_code = None
    contact_request.failure_detail = None
    logger.info(
        "contact_request_pending_cleared",
        request_id=contact_request.id,
        from_qiao_id=contact_request.from_qiao_id,
        to_qiao_id=contact_request.to_qiao_id,
    )


async def _get_active_square_category_title(
    db: AsyncSession, *, category_key: str | None
) -> str | None:
    if not category_key:
        return None
    result = await db.execute(
        select(SquareCategory.title).where(
            SquareCategory.category_key == category_key,
            SquareCategory.status == 1,
        )
    )
    title = result.scalar_one_or_none()
    return title if isinstance(title, str) else None


def _build_ai_contact_tags(
    *,
    override_tags: list[str] | None,
    category_title: str | None,
    persona_tags_payload: JSONValue | None,
) -> list[str] | None:
    if override_tags is not None:
        normalized = normalize_contact_tags(override_tags) or []
        tag_error = validate_tags(normalized)
        if tag_error is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=tag_error)
        return normalized

    combined: list[str] = []
    if category_title is not None and category_title.strip() != "":
        combined.append(category_title)

    if persona_tags_payload is not None:
        persona_tags = extract_request_tags(persona_tags_payload)
        if persona_tags is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "CONTACT_PRESET_INVALID"},
            )
        combined.extend(persona_tags)

    normalized = normalize_contact_tags(combined) or []
    tag_error = validate_tags(normalized)
    if tag_error is not None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "CONTACT_PRESET_INVALID"},
        )
    return normalized


def _map_request_source_to_contact(source: int | None) -> ContactSource:
    """Normalize contact request source enum into contacts.source enum."""
    if source is None:
        return ContactSource.UNKNOWN
    try:
        enum_value = ContactRequestSource(source)
    except ValueError:
        return ContactSource.UNKNOWN

    mapping = {
        ContactRequestSource.SEARCH: ContactSource.SEARCH,
        ContactRequestSource.ADMIN: ContactSource.ADMIN,
        ContactRequestSource.SYSTEM: ContactSource.SYSTEM,
        ContactRequestSource.RECOMMEND: ContactSource.RECOMMEND,
    }
    return mapping.get(enum_value, ContactSource.UNKNOWN)


async def _create_contact_record(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    user_id: int,
    contact_qiao_id: str,
    contact_id: int,
    contact_type: ContactType,
    conversation_id: str,
    alias: str | None,
    tags: list[str] | None,
    remark: str | None,
    source: ContactSource | None,
) -> Contact:
    """Create contact record from resolved request decision."""
    contact_data = ContactCreate(
        contact_type=contact_type,
        contact_qiao_id=contact_qiao_id,
        alias=alias,
        custom_avatar_key=None,
        custom_avatar_media_id=None,
        tags=tags,
        remark=remark,
        source=source if source is not None else ContactSource.UNKNOWN,
    )

    contact = await contact_crud.create_with_user(
        db,
        obj_in=contact_data,
        user_qiao_id=user_qiao_id,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    contact.contact_id = contact_id
    db.add(contact)
    return contact


def _handle_ai_decline(contact_request: ContactRequest, decision: ContactRequestDecision) -> None:
    """Apply failure metadata for AI declines."""
    if decision.reason == "WAIT_TEMPLATE" and decision.persona:
        failure_code = decision.pending_failure_code
        if not isinstance(failure_code, str):
            failure_code = ContactRequestFailureCode.NO_TEMPLATE_AVAILABLE.value
        mark_pending_failure(
            contact_request,
            persona=decision.persona,
            reason=failure_code,
        )
    else:
        contact_request.status = ContactRequestStatus.IGNORED
        contact_request.failure_code = None
        contact_request.failure_detail = None


async def process_ai_contact_request(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    user_id: int,
    contact_request: ContactRequest,
    alias: str | None,
    tags: list[str] | None,
    selected_template_override: AITemplate | None = None,
    suppress_instance_ai_type: bool = False,
    ai_type_suppressed_reason: str | None = None,
    mark_failed_on_unexpected_error: bool = True,
) -> JSONDict:
    """Process AI contact request and update state atomically."""
    request_id = contact_request.id
    to_qiao_id = contact_request.to_qiao_id
    conversation_id: str | None = None
    ai_qiao_id: str | None = None
    contact_id: int | None = None

    try:
        locked_request = await contact_request_crud.get_for_update(
            db, request_id=contact_request.id
        )
        if not locked_request:
            logger.error("contact_request_missing_for_processing", request_id=request_id)
            return {"message": "请求已发送"}

        contact_request = locked_request
        decision = await handle_ai_contact_request(
            db=db,
            request_id=contact_request.id,
            user_id=user_id,
            from_qiao_id=user_qiao_id,
            to_qiao_id=contact_request.to_qiao_id,
            message=contact_request.message or "",
        )

        if selected_template_override is not None and decision.persona is not None:
            decision = ContactRequestDecision(
                accepted=True,
                reason="FORCED_TEMPLATE",
                persona=decision.persona,
                template=selected_template_override,
            )

        if not decision.accepted or not decision.persona or not decision.template:
            _handle_ai_decline(contact_request, decision)
            await db.commit()
            logger.info(
                "ai_contact_request_ignored",
                request_id=request_id,
                user_qiao_id=user_qiao_id,
                to_qiao_id=to_qiao_id,
                reason=decision.reason,
            )
            return {"message": "请求已发送"}

        await db.execute(select(User).where(User.id == user_id).with_for_update())

        available_total = await get_ai_contact_limit_by_user_id(db, user_id=user_id)
        if available_total <= 0:
            contact_request.status = ContactRequestStatus.IGNORED
            contact_request.failure_code = None
            contact_request.failure_detail = None
            await db.commit()
            logger.warning(
                "ai_contact_limit_exceeded_worker",
                request_id=request_id,
                user_qiao_id=user_qiao_id,
                available_total=available_total,
            )
            return {"message": "请求已发送"}

        ai_instance = await create_instance_from_persona(
            db=db,
            persona=decision.persona,
            template=decision.template,
            user_id=user_id,
            user_qiao_id=user_qiao_id,
            suppress_ai_type_metadata=suppress_instance_ai_type,
            ai_type_suppressed_reason=ai_type_suppressed_reason,
        )

        conversation_id = f"conv_{generate_snowflake_id()}"
        category_title = (
            await _get_active_square_category_title(db, category_key=contact_request.category_key)
            if tags is None
            else None
        )
        effective_tags = _build_ai_contact_tags(
            override_tags=tags,
            category_title=category_title,
            persona_tags_payload=decision.persona.tags,
        )
        preset_remark = decision.persona.remark
        if isinstance(preset_remark, str) and preset_remark.strip() == "":
            preset_remark = None
        if preset_remark is not None:
            remark_error = validate_text_limit(preset_remark, CONTACT_REMARK_RULE)
            if remark_error is not None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"message": "CONTACT_PRESET_INVALID"},
                )

        contact = await _create_contact_record(
            db=db,
            user_qiao_id=user_qiao_id,
            user_id=user_id,
            contact_qiao_id=ai_instance.qiao_id,
            contact_id=ai_instance.id,
            contact_type=ContactType.AI,
            conversation_id=conversation_id,
            alias=alias,
            tags=effective_tags,
            remark=preset_remark,
            source=_map_request_source_to_contact(contact_request.source),
        )

        contact_request.status = ContactRequestStatus.ACCEPTED
        contact_request.to_id = ai_instance.id
        clear_pending_failure(contact_request)

        await consume_entitlement(
            db,
            user_id=user_id,
            entitlement_type_code=ENTITLEMENT_AI_CONTACT_LIMIT,
            value=1,
            source_type=ENTITLEMENT_SOURCE_CONTACT_AI_SLOT,
            source_id=contact.id,
            idempotency_key=f"contact_ai_consume:{contact.id}",
            event_payload={
                "request_id": request_id,
                "conversation_id": conversation_id,
                "contact_qiao_id": ai_instance.qiao_id,
            },
        )

        ai_qiao_id = decision.persona.qiao_id
        contact_id = contact.id
        content = CHAT_INFO_TEMPLATES[ChatInfoType.CONTACT_ADDED]
        await send_chat_info(
            db=db,
            to_qiao_id=user_qiao_id,
            conversation_id=conversation_id,
            content=content,
        )
        await db.commit()

        logger.info(
            "ai_contact_added",
            request_id=request_id,
            user_qiao_id=user_qiao_id,
            ai_qiao_id=ai_qiao_id,
            contact_id=contact_id,
        )
        return {"message": "请求已发送"}

    except Exception as exc:
        await db.rollback()
        if mark_failed_on_unexpected_error:
            try:
                failed_request = await contact_request_crud.get_for_update(
                    db, request_id=request_id
                )
                if failed_request is not None:
                    failed_request.status = ContactRequestStatus.FAILED
                    await db.commit()
            except Exception as commit_error:
                logger.error(
                    "failed_to_mark_failed",
                    request_id=request_id,
                    error=str(commit_error),
                )

        logger.error(
            "ai_contact_request_failed_system_error",
            request_id=request_id,
            user_qiao_id=user_qiao_id,
            to_qiao_id=to_qiao_id,
            error=str(exc),
            exc_info=True,
        )
        raise

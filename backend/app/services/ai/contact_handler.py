"""
AI contact request handler.

This module evaluates whether an AI persona can accept a contact request.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import AIPersonaStatus, AITemplateStatus, ReusableStatus
from app.models.ai.instance import AIInstance
from app.models.ai.template import AIPersona, AITemplate
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ContactRequestDecision:
    """Contact request decision result."""

    accepted: bool
    reason: str = ""
    pending_failure_code: str | None = None
    persona: AIPersona | None = None
    template: AITemplate | None = None


async def handle_ai_contact_request(
    db: AsyncSession,
    *,
    request_id: int,
    user_id: int,
    from_qiao_id: str,
    to_qiao_id: str,
    message: str,  # noqa: ARG001 - Reserved for contact request message validation
) -> ContactRequestDecision:
    """
    Handle contact request for a persona.

    Determines whether the requested persona is available and selects
    an appropriate template for instantiation.

    Args:
        message: Reserved for future use (contact request message validation)
    """

    persona = await _lock_persona_by_qiao_id(db, qiao_id=to_qiao_id)
    if not persona:
        logger.error(
            "persona_not_found",
            request_id=request_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
        )
        return ContactRequestDecision(
            accepted=False,
            reason="PERSONA_NOT_FOUND",
        )

    if int(persona.status) != AIPersonaStatus.ACTIVE:
        logger.info(
            "persona_inactive",
            request_id=request_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            persona_status=persona.status,
        )
        return ContactRequestDecision(
            accepted=False,
            reason="PERSONA_INACTIVE",
        )

    template, pending_failure_code = await _select_template_for_ai_type(
        db, type_id=persona.type_id, user_id=user_id
    )
    if not template:
        logger.info(
            "no_template_available",
            request_id=request_id,
            user_id=user_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            type_id=persona.type_id,
            failure_code=pending_failure_code,
        )
        return ContactRequestDecision(
            accepted=False,
            reason="WAIT_TEMPLATE",
            pending_failure_code=pending_failure_code,
            persona=persona,
        )

    logger.info(
        "ai_contact_request_accepted",
        request_id=request_id,
        from_qiao_id=from_qiao_id,
        to_qiao_id=to_qiao_id,
        persona_id=persona.id,
        template_id=template.id,
    )

    return ContactRequestDecision(
        accepted=True,
        persona=persona,
        template=template,
    )


async def _lock_persona_by_qiao_id(db: AsyncSession, *, qiao_id: str) -> AIPersona | None:
    """Lock persona row for update by qiao_id."""

    stmt = (
        select(AIPersona)
        .where(AIPersona.qiao_id == qiao_id)
        .options(selectinload(AIPersona.ai_type))
        .with_for_update()
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _select_template_for_ai_type(
    db: AsyncSession, *, type_id: int, user_id: int
) -> tuple[AITemplate | None, str | None]:
    """Select a template for the AI type, preferring single-use templates.

    Selection strategy:
    0. Exclude templates already used by the current user
    1. Prioritize single-use templates over reusable ones
    2. Sort by priority ASC (lower number = higher priority)
    3. If multiple templates share the highest priority, randomly select one
    """

    random_fn: Callable[[], Any] = cast(Callable[[], Any], func.random)
    used_template_subquery = select(AIInstance.template_id).where(
        AIInstance.user_id == user_id,
        AIInstance.template_id.is_not(None),
    )
    available_conditions = (
        AITemplate.type_id == type_id,
        AITemplate.status == AITemplateStatus.ACTIVE,
        ~AITemplate.id.in_(used_template_subquery),
    )

    single_use_stmt = (
        select(AITemplate)
        .where(
            *available_conditions,
            AITemplate.is_reusable == ReusableStatus.SINGLE_USE,
        )
        .options(selectinload(AITemplate.ai_type))
        .order_by(AITemplate.priority.asc(), random_fn())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(single_use_stmt)
    template = result.scalar_one_or_none()
    if template:
        return template, None

    reusable_stmt = (
        select(AITemplate)
        .where(
            *available_conditions,
            AITemplate.is_reusable == ReusableStatus.REUSABLE,
        )
        .options(selectinload(AITemplate.ai_type))
        .order_by(AITemplate.priority.asc(), random_fn())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    reusable_result = await db.execute(reusable_stmt)
    reusable_template = reusable_result.scalar_one_or_none()
    if reusable_template:
        return reusable_template, None

    has_available_stmt = select(AITemplate.id).where(*available_conditions).limit(1)
    has_available_result = await db.execute(has_available_stmt)
    if has_available_result.scalar_one_or_none() is not None:
        return None, "NO_TEMPLATE_AVAILABLE"

    has_active_stmt = (
        select(AITemplate.id)
        .where(
            AITemplate.type_id == type_id,
            AITemplate.status == AITemplateStatus.ACTIVE,
        )
        .limit(1)
    )
    has_active_result = await db.execute(has_active_stmt)
    if has_active_result.scalar_one_or_none() is not None:
        return None, "ALL_TEMPLATES_ALREADY_USED"

    return None, "NO_TEMPLATE_AVAILABLE"

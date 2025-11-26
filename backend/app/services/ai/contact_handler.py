"""
AI contact request handler.

This module evaluates whether an AI persona can accept a contact request.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums import AIPersonaStatus, AITemplateStatus, ReusableStatus
from models.ai.template import AIPersona, AITemplate
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ContactRequestDecision:
    """Contact request decision result."""

    accepted: bool
    reason: str = ""
    persona: Optional[AIPersona] = None
    template: Optional[AITemplate] = None


async def handle_ai_contact_request(
    db: AsyncSession,
    *,
    request_id: int,
    from_qiao_id: str,
    to_qiao_id: str,
    message: str,
) -> ContactRequestDecision:
    """
    Handle contact request for a persona.

    Determines whether the requested persona is available and selects
    an appropriate template for instantiation.
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

    template = await _select_template_for_ai_type(db, type_id=persona.type_id)
    if not template:
        logger.info(
            "no_template_available",
            request_id=request_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            type_id=persona.type_id,
        )
        return ContactRequestDecision(
            accepted=False,
            reason="WAIT_TEMPLATE",
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


async def _lock_persona_by_qiao_id(db: AsyncSession, *, qiao_id: str) -> Optional[AIPersona]:
    """Lock persona row for update by qiao_id."""

    stmt = select(AIPersona).where(AIPersona.qiao_id == qiao_id).with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _select_template_for_ai_type(db: AsyncSession, *, type_id: int) -> Optional[AITemplate]:
    """Select a template for the AI type, preferring single-use templates.

    Selection strategy:
    1. Prioritize single-use templates over reusable ones
    2. Sort by priority DESC (higher number = higher priority)
    3. If multiple templates share the highest priority, randomly select one
    """

    single_use_stmt = (
        select(AITemplate)
        .where(
            AITemplate.type_id == type_id,
            AITemplate.status == AITemplateStatus.ACTIVE,
            AITemplate.is_reusable == ReusableStatus.SINGLE_USE,
        )
        .order_by(AITemplate.priority.desc(), func.random())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(single_use_stmt)
    template = result.scalar_one_or_none()
    if template:
        return template

    reusable_stmt = (
        select(AITemplate)
        .where(
            AITemplate.type_id == type_id,
            AITemplate.status == AITemplateStatus.ACTIVE,
            AITemplate.is_reusable == ReusableStatus.REUSABLE,
        )
        .order_by(AITemplate.priority.desc(), func.random())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    reusable_result = await db.execute(reusable_stmt)
    return reusable_result.scalar_one_or_none()

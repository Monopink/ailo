"""Shared invitation intake orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.invite import invite_code as invite_code_crud
from app.crud.invite import invite_event as invite_event_crud
from app.crud.invite import invite_intake_log as invite_intake_log_crud
from app.enums.invite import InviteEventType
from app.models.system.runtime_observation import ClientRuntimeObservation
from app.services.invitation.bindability import is_invite_code_bindable
from app.services.invitation.intake import (
    normalize_event_source_or_raise,
    normalize_trigger_or_raise,
    resolve_intake_candidate,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

RECOGNITION_LOG_DEDUP_WINDOW_SECONDS = 600
IntakeMode = Literal["auth", "public"]


@dataclass(frozen=True)
class IntakeOrchestrationResult:
    """Unified intake orchestration result."""

    recognized_code: str | None
    valid: bool
    bindable: bool


def _log_fields_for_actor(*, actor_user_id: int | None) -> dict[str, object]:
    """Build log fields by actor identity availability."""
    if actor_user_id is None:
        return {}
    return {"user_id": actor_user_id}


def _core_failed_log_key(*, mode: IntakeMode) -> str:
    """Resolve core-failure log key by intake mode."""
    if mode == "public":
        return "public_invite_intake_core_failed"
    return "invite_intake_core_failed"


def _record_failed_log_key(*, mode: IntakeMode) -> str:
    """Resolve record-failure log key by intake mode."""
    if mode == "public":
        return "public_invite_intake_record_failed"
    return "invite_intake_record_failed"


async def _resolve_linked_runtime_observation_id(
    db: AsyncSession, *, runtime_observation_id: int | None
) -> int | None:
    """Return a FK-safe runtime observation id, otherwise null."""
    if runtime_observation_id is None:
        return None
    row = await db.execute(
        select(ClientRuntimeObservation.id).where(
            ClientRuntimeObservation.id == runtime_observation_id
        )
    )
    if row.first() is None:
        logger.info(
            "invite_intake_runtime_observation_missing",
            runtime_observation_id=runtime_observation_id,
        )
        return None
    return runtime_observation_id


async def orchestrate_invitation_intake(
    db: AsyncSession,
    *,
    mode: IntakeMode,
    source: str,
    trigger: str,
    raw_text: str | None,
    invite_code: str | None,
    actor_user_id: int | None,
    reviewer_flag_snapshot: int = 0,
    runtime_observation_id: int | None = None,
    client_user_agent: str = "",
    client_device_id: str = "",
) -> IntakeOrchestrationResult:
    """Run intake flow for authenticated/public invitation recognition."""
    normalized_source = normalize_event_source_or_raise(source)
    normalized_trigger = normalize_trigger_or_raise(trigger)
    intake_candidate = resolve_intake_candidate(raw_text=raw_text, invite_code=invite_code)

    recognized_code: str | None = None
    invite_code_id: int | None = None
    valid = False
    bindable = False
    normalized_raw_text = (raw_text or "").strip()

    try:
        if intake_candidate.normalized_code is not None:
            code_record = await invite_code_crud.get_active_by_code(
                db, code=intake_candidate.normalized_code
            )
            if code_record is not None:
                recognized_code = intake_candidate.normalized_code
                invite_code_id = int(code_record.id)
                valid = True
                if actor_user_id is not None:
                    bindable = await is_invite_code_bindable(
                        db,
                        invitee_user_id=actor_user_id,
                        inviter_user_id=int(code_record.owner_user_id),
                    )
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(
            _core_failed_log_key(mode=mode),
            source=normalized_source,
            trigger=normalized_trigger,
            error=str(exc),
            exc_info=True,
            **_log_fields_for_actor(actor_user_id=actor_user_id),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")

    try:
        linked_runtime_observation_id = await _resolve_linked_runtime_observation_id(
            db,
            runtime_observation_id=runtime_observation_id,
        )
        is_recent_duplicate = await invite_intake_log_crud.exists_recent_duplicate(
            db,
            actor_user_id=actor_user_id,
            source=normalized_source,
            trigger=normalized_trigger,
            raw_text=normalized_raw_text,
            first_candidate=intake_candidate.first_candidate,
            runtime_observation_id=linked_runtime_observation_id,
            client_user_agent=client_user_agent,
            client_device_id=client_device_id,
            within_seconds=RECOGNITION_LOG_DEDUP_WINDOW_SECONDS,
        )

        if valid and invite_code_id is not None and recognized_code is not None:
            if not is_recent_duplicate:
                await invite_event_crud.create_event(
                    db,
                    event_type=int(InviteEventType.OPEN),
                    actor_user_id=actor_user_id,
                    invite_code_id=invite_code_id,
                    event_source=normalized_source,
                    code_snapshot=recognized_code,
                    event_payload={"trigger": normalized_trigger},
                )

        if not is_recent_duplicate:
            log_bindable: bool | None
            if actor_user_id is None:
                log_bindable = None
            else:
                log_bindable = bindable if valid else False
            await invite_intake_log_crud.create_log(
                db,
                actor_user_id=actor_user_id,
                source=normalized_source,
                trigger=normalized_trigger,
                raw_text=normalized_raw_text,
                first_candidate=intake_candidate.first_candidate,
                recognized_code=recognized_code,
                invite_code_id=invite_code_id,
                valid=valid,
                bindable=log_bindable,
                reviewer_flag_snapshot=1 if reviewer_flag_snapshot == 1 else 0,
                runtime_observation_id=linked_runtime_observation_id,
                client_user_agent=client_user_agent.strip(),
                client_device_id=client_device_id.strip(),
            )
    except Exception as exc:
        await db.rollback()
        logger.warning(
            _record_failed_log_key(mode=mode),
            source=normalized_source,
            trigger=normalized_trigger,
            error=str(exc),
            **_log_fields_for_actor(actor_user_id=actor_user_id),
        )

    return IntakeOrchestrationResult(
        recognized_code=recognized_code,
        valid=valid,
        bindable=bindable if valid else False,
    )

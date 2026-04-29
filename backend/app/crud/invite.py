"""Invite code related CRUD operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.invite import InviteCodeStatus, InviteEventType
from app.models.invite import (
    InviteBinding,
    InviteCode,
    InviteEvent,
    InviteIntakeLog,
)


class CRUDInviteCode:
    """CRUD helpers for invite_codes."""

    async def get_by_owner_user_id(self, db: AsyncSession, *, user_id: int) -> InviteCode | None:
        """Return active invite code owned by the given user."""
        result = await db.execute(
            select(InviteCode).where(
                InviteCode.owner_user_id == user_id,
                InviteCode.status == int(InviteCodeStatus.ACTIVE),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, db: AsyncSession, *, code: str) -> InviteCode | None:
        """Return invite code record regardless of status."""
        result = await db.execute(select(InviteCode).where(InviteCode.code == code))
        return result.scalar_one_or_none()

    async def get_active_by_code(
        self,
        db: AsyncSession,
        *,
        code: str,
        for_update: bool = False,
    ) -> InviteCode | None:
        """Return active invite code by code value."""
        stmt = select(InviteCode).where(
            InviteCode.code == code,
            InviteCode.status == int(InviteCodeStatus.ACTIVE),
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user_code(self, db: AsyncSession, *, user_id: int, code: str) -> InviteCode:
        """Create one active invite code for a user."""
        obj = InviteCode(
            code=code,
            owner_user_id=user_id,
            status=int(InviteCodeStatus.ACTIVE),
        )
        db.add(obj)
        await db.flush()
        return obj


class CRUDInviteBinding:
    """CRUD helpers for invite_bindings."""

    async def get_by_invitee_user_id(
        self,
        db: AsyncSession,
        *,
        invitee_user_id: int,
    ) -> InviteBinding | None:
        """Return existing binding by invitee user id."""
        result = await db.execute(
            select(InviteBinding).where(InviteBinding.invitee_user_id == invitee_user_id)
        )
        return result.scalar_one_or_none()

    async def is_inviter_of(
        self,
        db: AsyncSession,
        *,
        inviter_user_id: int,
        invitee_user_id: int,
    ) -> bool:
        """Check whether inviter has invited the target invitee."""
        result = await db.execute(
            select(InviteBinding.id).where(
                InviteBinding.inviter_user_id_snapshot == inviter_user_id,
                InviteBinding.invitee_user_id == invitee_user_id,
            )
        )
        return result.first() is not None

    async def create_binding(
        self,
        db: AsyncSession,
        *,
        invitee_user_id: int,
        invite_code_id: int,
        code_snapshot: str,
        inviter_user_id_snapshot: int,
    ) -> InviteBinding:
        """Create one invite binding record."""
        obj = InviteBinding(
            invitee_user_id=invitee_user_id,
            invite_code_id=invite_code_id,
            code_snapshot=code_snapshot,
            inviter_user_id_snapshot=inviter_user_id_snapshot,
        )
        db.add(obj)
        await db.flush()
        return obj

    async def get_with_inviter_by_invitee_user_id(
        self,
        db: AsyncSession,
        *,
        invitee_user_id: int,
    ) -> tuple[int, int] | None:
        """Return binding id and inviter user id for one invitee."""
        result = await db.execute(
            select(InviteBinding.id, InviteBinding.inviter_user_id_snapshot).where(
                InviteBinding.invitee_user_id == invitee_user_id
            )
        )
        row = result.first()
        if row is None:
            return None
        return int(row[0]), int(row[1])

    async def count_success_by_inviter_user_id(
        self,
        db: AsyncSession,
        *,
        inviter_user_id: int,
    ) -> int:
        """Count successful invite bindings by inviter user id."""
        result = await db.execute(
            select(func.count(InviteBinding.id)).where(
                InviteBinding.inviter_user_id_snapshot == inviter_user_id
            )
        )
        count_value = result.scalar_one()
        return int(count_value or 0)


class CRUDInviteEvent:
    """CRUD helpers for invite_events."""

    async def exists_open_event(
        self,
        db: AsyncSession,
        *,
        actor_user_id: int,
        invite_code_id: int,
    ) -> bool:
        """Check whether actor already has an OPEN event for this invite code."""
        result = await db.execute(
            select(InviteEvent.id)
            .where(
                InviteEvent.event_type == int(InviteEventType.OPEN),
                InviteEvent.actor_user_id == actor_user_id,
                InviteEvent.invite_code_id == invite_code_id,
            )
            .limit(1)
        )
        return result.first() is not None

    async def create_event(
        self,
        db: AsyncSession,
        *,
        event_type: int,
        actor_user_id: int | None,
        invite_code_id: int | None,
        event_source: str,
        code_snapshot: str | None,
        event_payload: dict[str, object] | None,
    ) -> InviteEvent:
        """Create one invite event log row."""
        obj = InviteEvent(
            event_type=event_type,
            actor_user_id=actor_user_id,
            invite_code_id=invite_code_id,
            event_source=event_source,
            code_snapshot=code_snapshot,
            event_payload=event_payload,
        )
        db.add(obj)
        await db.flush()
        return obj


class CRUDInviteIntakeLog:
    """CRUD helpers for invite_intake_logs."""

    async def exists_recent_duplicate(
        self,
        db: AsyncSession,
        *,
        actor_user_id: int | None,
        source: str,
        trigger: str,
        raw_text: str,
        first_candidate: str | None,
        runtime_observation_id: int | None = None,
        client_user_agent: str = "",
        client_device_id: str = "",
        within_seconds: int = 2,
    ) -> bool:
        """Check whether an equivalent intake log exists in a short recent window."""
        normalized_window_seconds = max(within_seconds, 1)
        threshold = datetime.now(UTC) - timedelta(seconds=normalized_window_seconds)

        stmt = select(InviteIntakeLog.id).where(
            InviteIntakeLog.source == source,
            InviteIntakeLog.trigger == trigger,
            InviteIntakeLog.raw_text == raw_text,
            InviteIntakeLog.created_at >= threshold,
        )
        if first_candidate is None:
            stmt = stmt.where(InviteIntakeLog.first_candidate.is_(None))
        else:
            stmt = stmt.where(InviteIntakeLog.first_candidate == first_candidate)
        if actor_user_id is None:
            stmt = stmt.where(InviteIntakeLog.actor_user_id.is_(None))
            normalized_device_id = client_device_id.strip()
            if normalized_device_id != "":
                stmt = stmt.where(InviteIntakeLog.client_device_id == normalized_device_id)
            elif runtime_observation_id is not None:
                stmt = stmt.where(InviteIntakeLog.runtime_observation_id == runtime_observation_id)
            else:
                normalized_ua = client_user_agent.strip()
                if normalized_ua == "":
                    return False
                stmt = stmt.where(InviteIntakeLog.client_user_agent == normalized_ua)
        else:
            stmt = stmt.where(InviteIntakeLog.actor_user_id == actor_user_id)
        result = await db.execute(stmt.limit(1))
        return result.first() is not None

    async def create_log(
        self,
        db: AsyncSession,
        *,
        actor_user_id: int | None,
        source: str,
        trigger: str,
        raw_text: str,
        first_candidate: str | None,
        recognized_code: str | None,
        invite_code_id: int | None,
        valid: bool,
        bindable: bool | None,
        reviewer_flag_snapshot: int = 0,
        runtime_observation_id: int | None = None,
        client_user_agent: str = "",
        client_device_id: str = "",
    ) -> InviteIntakeLog:
        """Create one invite intake log row."""
        obj = InviteIntakeLog(
            actor_user_id=actor_user_id,
            source=source,
            trigger=trigger,
            raw_text=raw_text,
            first_candidate=first_candidate,
            recognized_code=recognized_code,
            invite_code_id=invite_code_id,
            valid=valid,
            bindable=bindable,
            reviewer_flag_snapshot=1 if reviewer_flag_snapshot == 1 else 0,
            runtime_observation_id=runtime_observation_id,
            client_user_agent=client_user_agent,
            client_device_id=client_device_id,
        )
        db.add(obj)
        await db.flush()
        return obj


invite_code = CRUDInviteCode()
invite_binding = CRUDInviteBinding()
invite_event = CRUDInviteEvent()
invite_intake_log = CRUDInviteIntakeLog()

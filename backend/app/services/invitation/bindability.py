"""Invitation bindability policy."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.invite import invite_binding as invite_binding_crud


async def is_invite_code_bindable(
    db: AsyncSession,
    *,
    invitee_user_id: int,
    inviter_user_id: int | None,
) -> bool:
    """Return whether invitee can bind the inviter's invite code."""
    existing = await invite_binding_crud.get_by_invitee_user_id(
        db,
        invitee_user_id=invitee_user_id,
    )
    if existing is not None:
        return False
    if inviter_user_id is None:
        return False
    if inviter_user_id == invitee_user_id:
        return False
    return not await invite_binding_crud.is_inviter_of(
        db,
        inviter_user_id=invitee_user_id,
        invitee_user_id=inviter_user_id,
    )

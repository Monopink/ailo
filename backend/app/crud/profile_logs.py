"""User profile change logging helpers (CRUD-level).

This module writes to user_profile_logs and provides helpers for computing
"stable old value" for prompt-building.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProfileModifierType, ProfileOwnerType
from app.models.profile import Profile, UserProfileLog


def _to_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _normalize_field_name(field_name: str) -> str:
    if field_name == "avatar_file_id":
        return "avatar_media_id"
    return field_name


def _read_value(profile: Profile | None, field_name: str) -> str | None:
    if profile is None:
        return None
    return _to_str(getattr(profile, field_name, None))


def _build_user_profile_log_row(
    *,
    owner_id: int,
    owner_qiao_id: str,
    owner_type: int,
    modified_by_type: ProfileModifierType,
    field_name: str,
    old_value: object,
    new_value: object,
    change_reason: str | None,
) -> UserProfileLog | None:
    if owner_type != int(ProfileOwnerType.USER):
        return None

    normalized = _normalize_field_name(field_name)
    old_str = _to_str(old_value)
    new_str = _to_str(new_value)
    if old_str == new_str:
        return None

    return UserProfileLog(
        owner_id=owner_id,
        owner_qiao_id=owner_qiao_id,
        owner_type=owner_type,
        modified_by_type=int(modified_by_type),
        field_name=normalized,
        old_value=old_str,
        new_value=new_str,
        change_reason=change_reason,
    )


async def write_user_profile_change_log(
    db: AsyncSession,
    *,
    owner_id: int,
    owner_qiao_id: str,
    owner_type: int,
    modified_by_type: ProfileModifierType,
    field_name: str,
    old_value: object,
    new_value: object,
    change_reason: str | None,
) -> None:
    """Insert a single user_profile_logs row when value changes.

    Caller controls transaction boundaries; this function only flushes.
    """
    row = _build_user_profile_log_row(
        owner_id=owner_id,
        owner_qiao_id=owner_qiao_id,
        owner_type=owner_type,
        modified_by_type=modified_by_type,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        change_reason=change_reason,
    )
    if row is None:
        return
    db.add(row)
    await db.flush()


async def write_user_profile_change_logs(
    db: AsyncSession,
    *,
    before: Profile | None,
    after: Profile,
    changed_fields: set[str],
    modified_by_type: ProfileModifierType,
    change_reason: str | None,
) -> None:
    """Insert one user_profile_logs row per changed field.

    Caller controls transaction boundaries; this function only flushes.
    """
    if not changed_fields:
        return
    if after.owner_type != int(ProfileOwnerType.USER):
        return

    for raw_field in sorted(changed_fields):
        field_name = _normalize_field_name(raw_field)
        old_value = _read_value(before, field_name)
        new_value = _read_value(after, field_name)
        row = _build_user_profile_log_row(
            owner_id=after.owner_id,
            owner_qiao_id=after.owner_qiao_id,
            owner_type=after.owner_type,
            modified_by_type=modified_by_type,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            change_reason=change_reason,
        )
        if row is None:
            continue
        db.add(row)

    await db.flush()


async def has_recent_profile_change(
    db: AsyncSession,
    *,
    owner_qiao_id: str,
    field_name: str,
    since: datetime,
) -> bool:
    """Return True if any change log exists for field since cutoff."""
    normalized = _normalize_field_name(field_name)
    result = await db.execute(
        select(UserProfileLog.id)
        .where(
            UserProfileLog.owner_qiao_id == owner_qiao_id,
            UserProfileLog.owner_type == int(ProfileOwnerType.USER),
            UserProfileLog.field_name == normalized,
            UserProfileLog.created_at >= since,
        )
        .order_by(UserProfileLog.created_at.desc(), UserProfileLog.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def find_stable_old_value(
    db: AsyncSession,
    *,
    owner_qiao_id: str,
    field_name: str,
    since: datetime,
    stable_duration: timedelta = timedelta(hours=6),
) -> tuple[bool, str | None]:
    """Return (changed, stable_old_value) for latest change since cutoff."""
    normalized = _normalize_field_name(field_name)
    result = await db.execute(
        select(UserProfileLog)
        .where(
            UserProfileLog.owner_qiao_id == owner_qiao_id,
            UserProfileLog.owner_type == int(ProfileOwnerType.USER),
            UserProfileLog.field_name == normalized,
            UserProfileLog.created_at >= since,
        )
        .order_by(UserProfileLog.created_at.desc(), UserProfileLog.id.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest is None:
        return False, None

    current_time = latest.created_at
    current_value = _to_str(latest.old_value)
    if current_value is None:
        return True, None

    while True:
        prev_result = await db.execute(
            select(UserProfileLog)
            .where(
                UserProfileLog.owner_qiao_id == owner_qiao_id,
                UserProfileLog.owner_type == int(ProfileOwnerType.USER),
                UserProfileLog.field_name == normalized,
                UserProfileLog.created_at < current_time,
            )
            .order_by(UserProfileLog.created_at.desc(), UserProfileLog.id.desc())
            .limit(1)
        )
        prev = prev_result.scalar_one_or_none()
        if prev is None:
            return True, current_value

        prev_new = _to_str(prev.new_value)
        duration = current_time - prev.created_at

        if prev_new == current_value and duration >= stable_duration:
            return True, current_value

        if prev_new != current_value:
            return True, current_value

        earlier_old = _to_str(prev.old_value)
        if earlier_old is None:
            return True, current_value

        current_time = prev.created_at
        current_value = earlier_old

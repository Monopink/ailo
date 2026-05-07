"""Profile integrity guards for user/persona/instance owners."""

from collections.abc import Set
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.profile import profile as profile_crud
from app.enums import ProfileOwnerType
from app.models.profile import Profile
from app.schemas.profile import ProfileCreate
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _require_owner_identity(*, owner_id: int | None, owner_qiao_id: str | None, label: str) -> None:
    if not isinstance(owner_qiao_id, str) or not owner_qiao_id:
        raise ValueError(f"{label} qiao_id is required to ensure profile integrity")
    if not isinstance(owner_id, int):
        raise TypeError(f"{label} id is required to ensure profile integrity")


async def _ensure_profile_for_owner(
    db: AsyncSession,
    *,
    owner_id: int,
    owner_qiao_id: str,
    owner_label: str,
    create_owner_type: ProfileOwnerType,
    allowed_existing_owner_types: Set[int],
    strict_owner_id_check_owner_types: Set[int],
    source: str,
    commit: bool,
    profile_in: ProfileCreate | None = None,
) -> Profile:
    existing = await profile_crud.get_by_owner_qiao_id(db, owner_qiao_id=owner_qiao_id)
    if existing is not None:
        existing_owner_type = int(existing.owner_type)
        if existing_owner_type not in allowed_existing_owner_types:
            raise ValueError(
                f"Existing profile owner_type is invalid for {owner_label} "
                f"(qiao_id={owner_qiao_id}, owner_type={existing_owner_type})"
            )
        if (
            existing_owner_type in strict_owner_id_check_owner_types
            and int(existing.owner_id) != owner_id
        ):
            raise ValueError(
                f"Existing {owner_label} profile owner_id does not match "
                f"(qiao_id={owner_qiao_id}, profile_owner_id={existing.owner_id}, "
                f"owner_id={owner_id})"
            )
        return existing

    created_profile = await profile_crud.create_with_owner(
        db,
        obj_in=profile_in or ProfileCreate(),
        owner_id=owner_id,
        owner_qiao_id=owner_qiao_id,
        owner_type=create_owner_type,
        commit=commit,
    )
    logger.debug(
        "profile_auto_created",
        owner_type=int(create_owner_type),
        owner_id=owner_id,
        owner_qiao_id=owner_qiao_id,
        source=source,
    )
    return created_profile


async def ensure_user_profile(
    db: AsyncSession,
    *,
    user_id: int | None,
    user_qiao_id: str | None,
    source: str,
    commit: bool = False,
    profile_in: ProfileCreate | None = None,
) -> Profile:
    """Ensure a user has a usable profile row."""
    _require_owner_identity(owner_id=user_id, owner_qiao_id=user_qiao_id, label="User")
    validated_user_id = cast(int, user_id)
    validated_user_qiao_id = cast(str, user_qiao_id)
    return await _ensure_profile_for_owner(
        db,
        owner_id=validated_user_id,
        owner_qiao_id=validated_user_qiao_id,
        owner_label="user",
        create_owner_type=ProfileOwnerType.USER,
        allowed_existing_owner_types={int(ProfileOwnerType.USER)},
        strict_owner_id_check_owner_types={int(ProfileOwnerType.USER)},
        source=source,
        commit=commit,
        profile_in=profile_in,
    )


async def ensure_persona_profile(
    db: AsyncSession,
    *,
    persona_id: int | None,
    persona_qiao_id: str | None,
    source: str,
    commit: bool = False,
    profile_in: ProfileCreate | None = None,
) -> Profile:
    """Ensure an AI persona has a usable profile row."""
    _require_owner_identity(owner_id=persona_id, owner_qiao_id=persona_qiao_id, label="AI persona")
    validated_persona_id = cast(int, persona_id)
    validated_persona_qiao_id = cast(str, persona_qiao_id)
    return await _ensure_profile_for_owner(
        db,
        owner_id=validated_persona_id,
        owner_qiao_id=validated_persona_qiao_id,
        owner_label="AI persona",
        create_owner_type=ProfileOwnerType.AI_PERSONA,
        allowed_existing_owner_types={int(ProfileOwnerType.AI_PERSONA)},
        strict_owner_id_check_owner_types={int(ProfileOwnerType.AI_PERSONA)},
        source=source,
        commit=commit,
        profile_in=profile_in,
    )


async def ensure_instance_profile(
    db: AsyncSession,
    *,
    instance_id: int | None,
    instance_qiao_id: str | None,
    source: str,
    commit: bool = False,
    profile_in: ProfileCreate | None = None,
) -> Profile:
    """Ensure an AI instance has a usable profile row."""
    _require_owner_identity(
        owner_id=instance_id,
        owner_qiao_id=instance_qiao_id,
        label="AI instance",
    )
    validated_instance_id = cast(int, instance_id)
    validated_instance_qiao_id = cast(str, instance_qiao_id)
    return await _ensure_profile_for_owner(
        db,
        owner_id=validated_instance_id,
        owner_qiao_id=validated_instance_qiao_id,
        owner_label="AI instance",
        create_owner_type=ProfileOwnerType.AI_INSTANCE,
        allowed_existing_owner_types={
            int(ProfileOwnerType.AI_PERSONA),
            int(ProfileOwnerType.AI_INSTANCE),
        },
        strict_owner_id_check_owner_types={int(ProfileOwnerType.AI_INSTANCE)},
        source=source,
        commit=commit,
        profile_in=profile_in,
    )

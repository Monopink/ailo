"""Profile integrity guards for AI instances."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.profile import profile as profile_crud
from app.enums import ProfileOwnerType
from app.models.ai.instance import AIInstance
from app.models.profile import Profile
from app.schemas.profile import ProfileCreate
from app.utils.logging import get_logger

logger = get_logger(__name__)

_ALLOWED_OWNER_TYPES = {
    int(ProfileOwnerType.AI_PERSONA),
    int(ProfileOwnerType.AI_INSTANCE),
}


async def ensure_instance_profile(
    db: AsyncSession,
    *,
    instance: AIInstance,
    source: str,
) -> Profile:
    """Ensure an AI instance has a usable profile row."""
    instance_qiao_id = getattr(instance, "qiao_id", None)
    instance_id = getattr(instance, "id", None)

    if not isinstance(instance_qiao_id, str) or not instance_qiao_id:
        raise ValueError("AI instance qiao_id is required to ensure profile integrity")
    if not isinstance(instance_id, int):
        raise TypeError("AI instance id is required to ensure profile integrity")

    profile_obj = await profile_crud.get_by_owner_qiao_id(db, owner_qiao_id=instance_qiao_id)
    if profile_obj is not None:
        owner_type = int(profile_obj.owner_type)
        if owner_type not in _ALLOWED_OWNER_TYPES:
            raise ValueError(
                "Existing profile owner_type is invalid for AI instance "
                f"(qiao_id={instance_qiao_id}, owner_type={owner_type})"
            )
        if (
            owner_type == int(ProfileOwnerType.AI_INSTANCE)
            and int(profile_obj.owner_id) != instance_id
        ):
            raise ValueError(
                "Existing instance profile owner_id does not match AI instance "
                f"(qiao_id={instance_qiao_id}, profile_owner_id={profile_obj.owner_id}, "
                f"instance_id={instance_id})"
            )
        return profile_obj

    created_profile = await profile_crud.create_with_owner(
        db,
        obj_in=ProfileCreate(),
        owner_id=instance_id,
        owner_qiao_id=instance_qiao_id,
        owner_type=ProfileOwnerType.AI_INSTANCE,
        commit=False,
    )
    logger.warning(
        "instance_profile_auto_created",
        instance_id=instance_id,
        instance_qiao_id=instance_qiao_id,
        source=source,
    )
    return created_profile

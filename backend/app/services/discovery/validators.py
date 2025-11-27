"""
Discovery admin validators.

Contains helpers shared between admin APIs and views.
"""

from enums import AIPersonaStatus, ProfileOwnerType
from models.ai import AIPersona
from models.profile import Profile
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def ensure_ai_type_has_active_persona(db: AsyncSession, type_id: int) -> None:
    """
    Ensure the selected AI type has at least one active persona with a profile.

    Raises:
        ValueError: if no persona/profile pair exists.
    """

    stmt = (
        select(func.count())
        .select_from(AIPersona)
        .join(
            Profile,
            and_(
                Profile.owner_qiao_id == AIPersona.qiao_id,
                Profile.owner_type == ProfileOwnerType.AI_PERSONA,
            ),
        )
        .where(
            and_(
                AIPersona.type_id == type_id,
                AIPersona.status == AIPersonaStatus.ACTIVE,
            )
        )
    )
    result = await db.execute(stmt)
    count = result.scalar() or 0
    if count == 0:
        raise ValueError("Selected AI type has no active persona with a profile")

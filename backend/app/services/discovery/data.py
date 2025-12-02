"""
Discovery data layer.

This module handles discovery page queries that rely on square exposure entries
and the corresponding AI persona profiles.
"""

from enums import AIPersonaStatus, ContactType, ProfileOwnerType, SquareEntryStatus
from models.ai import AIPersona
from models.contact import Contact
from models.discovery import SquareTypeEntry
from models.profile import Profile
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_random_persona_entries(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    category: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[SquareTypeEntry, AIPersona, Profile]], int]:
    """
    Select random square entries with pagination.

    Only active entries with an AI profile that the current user does not
    already have in contacts are returned.
    """
    try:
        page = max(page, 1)
        limit = max(page_size, 1)
        offset = (page - 1) * limit

        excluded_qiao_ids = (
            select(Contact.contact_qiao_id)
            .where(
                Contact.user_qiao_id == user_qiao_id,
                Contact.contact_type == ContactType.AI,
                Contact.is_deleted == 0,
            )
            .scalar_subquery()
        )

        base_conditions = [SquareTypeEntry.status == SquareEntryStatus.ACTIVE]
        if category is not None:
            base_conditions.append(SquareTypeEntry.square_category == category)

        total_query = (
            select(func.count()).select_from(SquareTypeEntry).where(and_(*base_conditions))
        )
        total_result = await db.execute(total_query)
        total = total_result.scalar() or 0

        data_query = (
            select(SquareTypeEntry)
            .where(and_(*base_conditions))
            .order_by(func.random())
            .offset(offset)
            .limit(limit)
        )

        result = await db.execute(data_query)
        square_entries = result.scalars().all()

        persona_cache: dict[int, tuple[AIPersona, Profile]] = {}
        resolved_entries: list[tuple[SquareTypeEntry, AIPersona, Profile]] = []

        for entry in square_entries:
            cached = persona_cache.get(entry.type_id)
            if cached is None:
                persona_profile = await _pick_persona_for_ai_type(
                    db,
                    type_id=entry.type_id,
                    excluded_qiao_ids=excluded_qiao_ids,
                )
                if not persona_profile:
                    logger.debug(
                        "square_entry_skipped_no_persona",
                        entry_id=entry.id,
                        type_id=entry.type_id,
                    )
                    continue
                persona_cache[entry.type_id] = persona_profile
                cached = persona_profile

            persona, profile = cached
            resolved_entries.append((entry, persona, profile))

        logger.debug(
            "square_entries_selected",
            user_qiao_id=user_qiao_id,
            category=category,
            requested_page=page,
            returned=len(resolved_entries),
            total=total,
        )

        return resolved_entries, total

    except Exception as exc:
        logger.error(
            "fetch_square_entries_failed",
            user_qiao_id=user_qiao_id,
            category=category,
            error=str(exc),
        )
        raise


async def get_persona_profile_by_qiao_id(
    db: AsyncSession,
    *,
    qiao_id: str,
) -> tuple[Profile | None, str | None]:
    """
    Load the AI persona profile along with its latest square category.
    """
    try:
        profile_stmt = select(Profile).where(
            Profile.owner_qiao_id == qiao_id,
            Profile.owner_type == ProfileOwnerType.AI_PERSONA,
        )
        profile_result = await db.execute(profile_stmt)
        profile = profile_result.scalar_one_or_none()

        if not profile:
            return None, None

        persona_stmt = select(AIPersona.type_id).where(
            AIPersona.qiao_id == qiao_id,
            AIPersona.status == AIPersonaStatus.ACTIVE,
        )
        persona_result = await db.execute(persona_stmt)
        type_id = persona_result.scalar_one_or_none()

        if type_id is None:
            return profile, None

        category_stmt = (
            select(SquareTypeEntry.square_category)
            .where(
                SquareTypeEntry.type_id == type_id,
                SquareTypeEntry.status == SquareEntryStatus.ACTIVE,
            )
            .limit(1)
        )
        category_result = await db.execute(category_stmt)
        category = category_result.scalar_one_or_none()

        return profile, category
    except Exception as exc:
        logger.error("fetch_persona_profile_failed", qiao_id=qiao_id, error=str(exc))
        raise


async def _pick_persona_for_ai_type(
    db: AsyncSession,
    *,
    type_id: int,
    excluded_qiao_ids,
) -> tuple[AIPersona, Profile] | None:
    """
    Pick an active persona + profile pair for the given AI type that is not already in the user's contacts.
    """

    stmt = (
        select(AIPersona, Profile)
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
                AIPersona.qiao_id.notin_(excluded_qiao_ids),
            )
        )
        .order_by(func.random())
        .limit(1)
    )

    result = await db.execute(stmt)
    row = result.first()
    if not row:
        return None
    persona, profile = row
    return persona, profile

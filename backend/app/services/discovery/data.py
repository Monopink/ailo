"""
Discovery data layer.

This module handles discovery page queries that rely on square exposure entries
and the corresponding AI persona profiles.
"""

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    SQUARE_CATEGORY_THEME_KEYS,
    AIPersonaStatus,
    ContactType,
    ProfileOwnerType,
    SquareCategoryStatus,
    SquareEntryStatus,
)
from app.models.ai import AIPersona
from app.models.contact import Contact
from app.models.content import SquareCategory, SquareTypeEntry
from app.models.profile import Profile
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def get_active_square_categories(db: AsyncSession) -> list[SquareCategory]:
    """Load active categories.

    Note: categories may be empty (no active square_type_entries).
    """

    stmt = (
        select(SquareCategory)
        .where(
            SquareCategory.status == SquareCategoryStatus.ACTIVE,
            SquareCategory.theme_key.in_(SQUARE_CATEGORY_THEME_KEYS),
        )
        .order_by(SquareCategory.sort_order.asc(), SquareCategory.category_key.asc())
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_random_persona_entries(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    category_key: str,
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

        excluded_result = await db.execute(
            select(Contact.contact_qiao_id).where(
                Contact.user_qiao_id == user_qiao_id,
                Contact.contact_type == ContactType.AI,
                Contact.is_deleted == 0,
            )
        )
        excluded_qiao_ids: list[str] = [
            qiao_id for qiao_id in excluded_result.scalars().all() if isinstance(qiao_id, str)
        ]

        base_conditions = [
            SquareTypeEntry.status == SquareEntryStatus.ACTIVE,
            SquareTypeEntry.category_key == category_key,
        ]

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
            category_key=category_key,
            requested_page=page,
            returned=len(resolved_entries),
            total=total,
        )

        return resolved_entries, total

    except Exception as exc:
        logger.error(
            "fetch_square_entries_failed",
            user_qiao_id=user_qiao_id,
            category_key=category_key,
            error=str(exc),
        )
        raise


async def get_persona_profile_by_qiao_id(
    db: AsyncSession,
    *,
    qiao_id: str,
    category_key: str | None = None,
) -> tuple[Profile | None, str | None, str | None]:
    """
    Load the AI persona profile and validate optional category context.
    """
    try:
        profile_stmt = select(Profile).where(
            Profile.owner_qiao_id == qiao_id,
            Profile.owner_type == ProfileOwnerType.AI_PERSONA,
        )
        profile_result = await db.execute(profile_stmt)
        profile = profile_result.scalar_one_or_none()

        if not profile:
            return None, None, None

        if category_key is None:
            return profile, None, None

        category_stmt = (
            select(SquareCategory.category_key, SquareCategory.title)
            .where(
                SquareCategory.category_key == category_key,
                SquareCategory.status == SquareCategoryStatus.ACTIVE,
                SquareCategory.theme_key.in_(SQUARE_CATEGORY_THEME_KEYS),
            )
            .limit(1)
        )
        category_result = await db.execute(category_stmt)
        category_row = category_result.first()
        if category_row is None:
            return profile, None, None
        return profile, category_row[0], category_row[1]
    except Exception as exc:
        logger.error(
            "fetch_persona_profile_failed",
            qiao_id=qiao_id,
            category_key=category_key,
            error=str(exc),
        )
        raise


async def _pick_persona_for_ai_type(
    db: AsyncSession,
    *,
    type_id: int,
    excluded_qiao_ids: list[str],
) -> tuple[AIPersona, Profile] | None:
    """
    Pick an active persona + profile pair for the given AI type
    that is not already in the user's contacts.
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
            )
        )
        .order_by(func.random())
        .limit(1)
    )

    if excluded_qiao_ids:
        stmt = stmt.where(AIPersona.qiao_id.notin_(excluded_qiao_ids))

    result = await db.execute(stmt)
    row = result.first()
    if not row:
        return None
    persona, profile = row
    return persona, profile

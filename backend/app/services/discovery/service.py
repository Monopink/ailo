"""
Discovery service business logic.

This module provides business logic for discovery page operations.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.system import system_configs
from app.enums import SquareCategoryTheme
from app.schemas.discovery import (
    PaginationInfo,
    SquareCategoryItem,
    SquareCategoryListResponse,
    SquareContactListResponse,
    SquareContactResponse,
    StrangerProfileResponse,
)
from app.services.discovery import data as discovery_data
from app.services.profile.avatar import get_avatar_url, get_avatar_urls_batch
from app.services.security.rate_limiter import check_rate_limit
from app.services.system_config import get_config_int
from app.type_defs import JSONValue
from app.utils.contact_tags import extract_tags_payload, normalize_tags, validate_tags
from app.utils.logging import get_logger
from app.utils.text_limits import CONTACT_REMARK_RULE, validate_text_limit

logger = get_logger(__name__)

_ERR_RATE_LIMIT_PREFIX = "RATE_LIMIT:"
_ERR_INVALID_CATEGORY = "INVALID_CATEGORY_KEY"


def _build_preset_tags(
    *, category_title: str | None, persona_tags_payload: JSONValue | None
) -> list[str]:
    combined: list[str] = []
    if isinstance(category_title, str) and category_title.strip():
        combined.append(category_title)

    if persona_tags_payload is not None:
        persona_tags = extract_tags_payload(persona_tags_payload)
        if persona_tags is None:
            raise RuntimeError("CONTACT_PRESET_INVALID")
        combined.extend(persona_tags)

    normalized = normalize_tags(combined) or []
    if validate_tags(normalized) is not None:
        raise RuntimeError("CONTACT_PRESET_INVALID")
    return normalized


def _normalize_preset_remark(raw_remark: str | None) -> str | None:
    if raw_remark is None:
        return None
    if raw_remark.strip() == "":
        return None
    remark_error = validate_text_limit(raw_remark, CONTACT_REMARK_RULE)
    if remark_error is not None:
        raise RuntimeError("CONTACT_PRESET_INVALID")
    return raw_remark


async def get_square_categories(db: AsyncSession) -> SquareCategoryListResponse:
    """Get active square categories for clients."""

    categories = await discovery_data.get_active_square_categories(db)
    items = [
        SquareCategoryItem(
            category_key=item.category_key,
            title=item.title,
            description=item.description,
            theme_key=SquareCategoryTheme(item.theme_key),
            icon_ref=item.icon_ref,
        )
        for item in categories
    ]
    return SquareCategoryListResponse(items=items)


async def get_square_contacts(
    db: AsyncSession,
    user_qiao_id: str,
    category_key: str,
    page: int = 1,
    page_size: int | None = None,
) -> SquareContactListResponse:
    """
    Get square page contacts with pagination.

    Args:
        db: Database session
        user_qiao_id: Current user's qiao_id
        category_key: Required category key filter
        page: Page number (1-indexed)
        page_size: Items per page (None = use config default)

    Returns:
        SquareContactListResponse with pagination info and refresh time

    Raises:
        ValueError: Invalid category key or rate limit exceeded
    """
    try:
        if page_size is None:
            page_size = _coerce_positive_int(
                await system_configs.get_config_value(
                    db, config_key="square_page_size", default_value=20
                ),
                default=20,
            )

        categories = await discovery_data.get_active_square_categories(db)
        category_keys = {item.category_key for item in categories}
        if category_key not in category_keys:
            raise ValueError(_ERR_INVALID_CATEGORY)

        rate_key = f"{user_qiao_id}:{category_key}"
        allowed, _error_code, retry_after = await check_rate_limit(
            identifier=rate_key, group="square", db=db
        )

        if not allowed:
            logger.warning(
                "square_rate_limit",
                user_qiao_id=user_qiao_id,
                category_key=category_key,
                retry_after=retry_after,
            )
            raise ValueError(f"{_ERR_RATE_LIMIT_PREFIX}{retry_after or 0}")

        entries, total = await discovery_data.get_random_persona_entries(
            db=db,
            user_qiao_id=user_qiao_id,
            category_key=category_key,
            page=page,
            page_size=page_size,
        )

        profiles = [profile for _, _, profile in entries if profile]
        avatar_urls = await get_avatar_urls_batch(profiles)
        category_title = next(
            (item.title for item in categories if item.category_key == category_key),
            None,
        )

        items = [
            SquareContactResponse(
                qiao_id=persona.qiao_id,
                type_id=entry.type_id,
                category_key=entry.category_key,
                nickname=getattr(profile, "nickname", None),
                gender=getattr(profile, "gender", None),
                avatar_url=avatar_urls.get(profile.id) if profile else None,
                tags=_build_preset_tags(
                    category_title=category_title,
                    persona_tags_payload=persona.tags,
                ),
                remark=_normalize_preset_remark(persona.remark),
                bio=getattr(profile, "bio", None),
                region=getattr(profile, "region", None),
            )
            for entry, persona, profile in entries
        ]

        has_more = (page * page_size) < total
        pagination = PaginationInfo(page=page, page_size=page_size, total=total, has_more=has_more)

        refresh_available_at = await _resolve_refresh_available_at(db)

        logger.info(
            "square_contacts_retrieved",
            user_qiao_id=user_qiao_id,
            count=len(items),
            category_key=category_key,
            page=page,
            total=total,
            refresh_available_at=(
                refresh_available_at.isoformat() if refresh_available_at else None
            ),
        )

        return SquareContactListResponse(
            items=items,
            pagination=pagination,
            refresh_available_at=refresh_available_at,
        )

    except ValueError:
        raise
    except Exception as exc:
        logger.error(
            "square_contacts_service_error",
            user_qiao_id=user_qiao_id,
            category_key=category_key,
            error=str(exc),
        )
        raise RuntimeError(f"Failed to get square contacts: {exc!s}") from exc


async def get_stranger_profile(
    db: AsyncSession,
    qiao_id: str,
    *,
    category_key: str | None = None,
) -> StrangerProfileResponse | None:
    """
    Get stranger profile by qiao_id.

    This is a public endpoint that returns basic persona metadata.
    """
    try:
        (
            persona,
            profile,
            valid_category_key,
            category_title,
        ) = await discovery_data.get_persona_profile_by_qiao_id(
            db=db,
            qiao_id=qiao_id,
            category_key=category_key,
        )

        if not profile or not persona:
            logger.warning("stranger_profile_not_found", qiao_id=qiao_id)
            return None

        avatar_url = await get_avatar_url(profile)
        response = StrangerProfileResponse(
            qiao_id=profile.owner_qiao_id,
            nickname=profile.nickname,
            gender=profile.gender,
            avatar_url=avatar_url,
            tags=_build_preset_tags(
                category_title=category_title,
                persona_tags_payload=persona.tags,
            ),
            remark=_normalize_preset_remark(persona.remark),
            bio=profile.bio,
            region=profile.region,
            category_key=valid_category_key,
            category_title=category_title,
        )

        logger.info(
            "stranger_profile_retrieved",
            qiao_id=qiao_id,
            category_key=valid_category_key,
        )
        return response
    except Exception as exc:
        logger.error(
            "stranger_profile_service_error",
            qiao_id=qiao_id,
            category_key=category_key,
            error=str(exc),
        )
        raise RuntimeError(f"Failed to get stranger profile: {exc!s}") from exc


async def _resolve_refresh_available_at(db: AsyncSession) -> datetime | None:
    """Resolve next refresh availability timestamp from rate-limit window config."""

    window_seconds = _coerce_non_negative_int(
        await system_configs.get_config_value(
            db,
            config_key="square_rate_limit_window_seconds",
            default_value=0,
        ),
        default=0,
    )
    if window_seconds <= 0:
        return None
    return datetime.now(UTC) + timedelta(seconds=window_seconds)


def _coerce_non_negative_int(value: JSONValue | None, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"Invalid integer configuration: {value!r}") from exc
    raise ValueError(f"Unsupported integer configuration type: {type(value).__name__}")


def _coerce_positive_int(value: JSONValue | None, *, default: int) -> int:
    coerced = _coerce_non_negative_int(value, default=default)
    if coerced <= 0:
        raise ValueError(f"Expected positive integer configuration, got {coerced!r}")
    return coerced

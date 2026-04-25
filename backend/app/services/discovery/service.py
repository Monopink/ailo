"""Discovery service business logic."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import SquareCategoryTheme
from app.schemas.discovery import (
    SquareCategoryItem,
    SquareCategoryListResponse,
    SquareContactListResponse,
    SquareContactResponse,
    StrangerProfileResponse,
)
from app.services.discovery import data as discovery_data
from app.services.media.config import get_media_base_url
from app.services.profile.avatar import get_avatar_url
from app.services.security.rate_limiter import check_rate_limit
from app.services.system_config import get_config_int
from app.type_defs import JSONValue
from app.utils.contact_tags import extract_tags_payload, normalize_tags, validate_tags
from app.utils.logging import get_logger
from app.utils.text_limits import CONTACT_REMARK_RULE, validate_text_limit

logger = get_logger(__name__)

_ERR_RATE_LIMIT_PREFIX = "RATE_LIMIT:"
_ERR_INVALID_CATEGORY = "INVALID_CATEGORY_KEY"
_DEFAULT_AVATAR_OBJECT_KEY = "avatars/default.webp"


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
    cursor: str | None = None,
    page_size: int | None = None,
    feed_version: str | None = None,
    refresh: bool = False,
) -> SquareContactListResponse:
    """
    Get square page contacts with feed cursor pagination.

    Args:
        db: Database session
        user_qiao_id: Current user's qiao_id
        category_key: Required category key filter
        cursor: Opaque cursor for loading additional entries
        page_size: Items per page (None = use config default)
        feed_version: Existing feed version for loading more
        refresh: Whether this request requests a new feed version

    Returns:
        SquareContactListResponse with feed cursor and refresh time

    Raises:
        ValueError: Invalid category key or rate limit exceeded
    """
    try:
        if page_size is None:
            page_size = await get_config_int(db, key="square_page_size")
            if page_size <= 0:
                raise ValueError(f"Expected positive integer configuration, got {page_size!r}")

        categories = await discovery_data.get_active_square_categories(db)
        category_keys = {item.category_key for item in categories}
        if category_key not in category_keys:
            raise ValueError(_ERR_INVALID_CATEGORY)

        rate_group = "square_refresh" if refresh else "square_load_more"
        rate_key = f"{user_qiao_id}:{category_key}"
        allowed, _error_code, retry_after = await check_rate_limit(
            identifier=rate_key, group=rate_group, db=db
        )

        if not allowed:
            logger.warning(
                "square_rate_limit",
                user_qiao_id=user_qiao_id,
                category_key=category_key,
                retry_after=retry_after,
            )
            raise ValueError(f"{_ERR_RATE_LIMIT_PREFIX}{retry_after or 0}")

        resolved_feed_version = _resolve_feed_version(
            feed_version=feed_version,
            refresh=refresh,
        )
        feed_page = await discovery_data.get_square_feed_page(
            db=db,
            user_qiao_id=user_qiao_id,
            category_key=category_key,
            feed_version=resolved_feed_version,
            cursor=None if refresh else cursor,
            page_size=page_size,
        )
        avatar_base = get_media_base_url()
        category_title = next(
            (item.title for item in categories if item.category_key == category_key),
            None,
        )

        items = [
            SquareContactResponse(
                qiao_id=record.qiao_id,
                type_id=record.type_id,
                category_key=category_key,
                nickname=record.nickname,
                gender=record.gender,
                avatar_url=f"{avatar_base}/{record.avatar_key or _DEFAULT_AVATAR_OBJECT_KEY}",
                tags=_build_preset_tags(
                    category_title=category_title,
                    persona_tags_payload=record.tags_payload,
                ),
                remark=_normalize_preset_remark(record.remark),
                bio=record.bio,
                region=record.region,
            )
            for record in feed_page.records
        ]
        refresh_available_at = await _resolve_refresh_available_at(db) if refresh else None

        logger.info(
            "square_contacts_retrieved",
            user_qiao_id=user_qiao_id,
            count=len(items),
            category_key=category_key,
            feed_version=resolved_feed_version,
            has_more=feed_page.has_more,
            candidate_count=feed_page.metrics.candidate_count,
            excluded_history_count=feed_page.metrics.excluded_history_count,
            duplicate_filtered_count=feed_page.metrics.duplicate_filtered_count,
            query_duration_ms=feed_page.metrics.query_duration_ms,
            refresh_available_at=(
                refresh_available_at.isoformat() if refresh_available_at else None
            ),
        )

        return SquareContactListResponse(
            items=items,
            feed_version=resolved_feed_version,
            next_cursor=feed_page.next_cursor,
            has_more=feed_page.has_more,
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

    window_seconds = await get_config_int(db, key="square_refresh_rate_limit_window_seconds")
    if window_seconds <= 0:
        return None
    return datetime.now(UTC) + timedelta(seconds=window_seconds)


def _resolve_feed_version(*, feed_version: str | None, refresh: bool) -> str:
    if refresh or not isinstance(feed_version, str) or not feed_version.strip():
        now = datetime.now(UTC)
        return now.strftime("%Y%m%d%H%M%S%f")
    return feed_version.strip()

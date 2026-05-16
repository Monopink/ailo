"""Discovery service business logic."""

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import SquareCategoryTheme
from app.models.user import User
from app.schemas.discovery import (
    SquareCategoryItem,
    SquareCategoryListResponse,
    SquareContactListResponse,
    SquareContactResponse,
    StrangerProfileResponse,
)
from app.services.discovery import data as discovery_data
from app.services.media.config import get_media_base_url
from app.services.minor_mode_policy import is_minor_mode_enabled
from app.services.profile.avatar import get_avatar_url
from app.services.review_scope_policy import resolve_visible_review_scopes
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


async def get_square_categories(
    db: AsyncSession,
    *,
    current_user: User,
) -> SquareCategoryListResponse:
    """Get active square categories for clients."""

    visible_review_scopes = resolve_visible_review_scopes(current_user)
    require_minor_visible = is_minor_mode_enabled(current_user)
    categories = await discovery_data.get_active_square_categories(
        db,
        visible_review_scopes=visible_review_scopes,
        require_minor_visible=require_minor_visible,
    )
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
    *,
    current_user: User,
    user_qiao_id: str,
    category_key: str,
    cursor: str | None = None,
    page_size: int | None = None,
) -> SquareContactListResponse:
    """
    Get square page contacts with feed cursor pagination.

    Args:
        db: Database session
        user_qiao_id: Current user's qiao_id
        category_key: Required category key filter
        cursor: Opaque cursor for loading additional entries
        page_size: Items per page (None = use config default)
    Returns:
        SquareContactListResponse with refresh status and page-limit semantics

    Raises:
        ValueError: Invalid category key or rate limit exceeded
    """
    try:
        if page_size is None:
            page_size = await get_config_int(db, key="square_page_size")
            if page_size <= 0:
                raise ValueError(f"Expected positive integer configuration, got {page_size!r}")

        visible_review_scopes = resolve_visible_review_scopes(current_user)
        require_minor_visible = is_minor_mode_enabled(current_user)
        categories = await discovery_data.get_active_square_categories(
            db,
            visible_review_scopes=visible_review_scopes,
            require_minor_visible=require_minor_visible,
        )
        category_keys = {item.category_key for item in categories}
        if category_key not in category_keys:
            raise ValueError(_ERR_INVALID_CATEGORY)

        refresh_interval_seconds = await get_config_int(
            db,
            key="square_refresh_interval_seconds",
        )
        max_pages_per_feed = await get_config_int(
            db,
            key="square_max_pages_per_feed",
        )
        resolved_max_pages_per_feed = max(1, max_pages_per_feed)

        now = datetime.now(UTC)
        persisted_state = await discovery_data.get_square_feed_state(
            db,
            user_qiao_id=user_qiao_id,
            category_key=category_key,
        )
        should_attempt_refresh = cursor is None and (
            persisted_state is None or persisted_state.next_refresh_available_at <= now
        )

        feed_state: discovery_data.SquareCategoryFeedState | None
        if cursor is not None:
            rate_key = f"{user_qiao_id}:{category_key}"
            allowed, _error_code, retry_after = await check_rate_limit(
                identifier=rate_key,
                group="square_load_more",
                db=db,
            )
            if not allowed:
                logger.warning(
                    "square_rate_limit",
                    user_qiao_id=user_qiao_id,
                    category_key=category_key,
                    retry_after=retry_after,
                    action="load_more",
                )
                raise ValueError(f"{_ERR_RATE_LIMIT_PREFIX}{retry_after or 0}")
            feed_state = persisted_state
        elif should_attempt_refresh:
            rate_key = f"{user_qiao_id}:{category_key}"
            allowed, _error_code, retry_after = await check_rate_limit(
                identifier=rate_key,
                group="square_refresh",
                db=db,
            )
            if not allowed and persisted_state is not None:
                logger.warning(
                    "square_refresh_rate_limit_degraded",
                    user_qiao_id=user_qiao_id,
                    category_key=category_key,
                    retry_after=retry_after,
                )
                feed_state = persisted_state
            else:
                feed_state = await discovery_data.get_or_refresh_square_feed_state(
                    db,
                    user_qiao_id=user_qiao_id,
                    category_key=category_key,
                    refresh_interval_seconds=refresh_interval_seconds,
                )
        else:
            feed_state = persisted_state

        if cursor is not None and feed_state is None:
            raise ValueError("INVALID_CURSOR")

        if feed_state is None:
            feed_state = await discovery_data.get_or_refresh_square_feed_state(
                db,
                user_qiao_id=user_qiao_id,
                category_key=category_key,
                refresh_interval_seconds=refresh_interval_seconds,
            )
            now = datetime.now(UTC)

        resolved_feed_version = feed_state.feed_version
        current_page_index = discovery_data.resolve_square_next_page_index(
            cursor=cursor,
            feed_version=resolved_feed_version,
        )

        can_refresh_now = now >= feed_state.next_refresh_available_at
        refresh_remaining_seconds = max(
            0,
            int((feed_state.next_refresh_available_at - now).total_seconds()),
        )

        if current_page_index > resolved_max_pages_per_feed:
            return SquareContactListResponse(
                items=[],
                next_cursor=None,
                has_more=False,
                current_page_index=current_page_index,
                max_pages_per_feed=resolved_max_pages_per_feed,
                end_reason="page_limit_reached",
                can_refresh_now=can_refresh_now,
                refresh_remaining_seconds=refresh_remaining_seconds,
                next_refresh_available_at=feed_state.next_refresh_available_at,
                refresh_interval_seconds=max(0, refresh_interval_seconds),
            )

        feed_page = await discovery_data.get_square_feed_page(
            db=db,
            user_qiao_id=user_qiao_id,
            category_key=category_key,
            feed_version=resolved_feed_version,
            current_page_index=current_page_index,
            cursor=cursor,
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

        resolved_has_more = feed_page.has_more
        resolved_next_cursor = feed_page.next_cursor
        end_reason: Literal["no_more_data", "page_limit_reached"] | None = None
        if current_page_index >= resolved_max_pages_per_feed:
            if feed_page.has_more:
                resolved_has_more = False
                resolved_next_cursor = None
                end_reason = "page_limit_reached"
            else:
                resolved_has_more = False
                resolved_next_cursor = None
                end_reason = "no_more_data"
        elif not feed_page.has_more:
            end_reason = "no_more_data"

        logger.info(
            "square_contacts_retrieved",
            user_qiao_id=user_qiao_id,
            count=len(items),
            category_key=category_key,
            feed_version=resolved_feed_version,
            has_more=resolved_has_more,
            current_page_index=current_page_index,
            max_pages_per_feed=resolved_max_pages_per_feed,
            end_reason=end_reason,
            candidate_count=feed_page.metrics.candidate_count,
            excluded_history_count=feed_page.metrics.excluded_history_count,
            duplicate_filtered_count=feed_page.metrics.duplicate_filtered_count,
            query_duration_ms=feed_page.metrics.query_duration_ms,
            next_refresh_available_at=feed_state.next_refresh_available_at.isoformat(),
            refresh_remaining_seconds=refresh_remaining_seconds,
        )

        return SquareContactListResponse(
            items=items,
            next_cursor=resolved_next_cursor,
            has_more=resolved_has_more,
            current_page_index=current_page_index,
            max_pages_per_feed=resolved_max_pages_per_feed,
            end_reason=end_reason,
            can_refresh_now=can_refresh_now,
            refresh_remaining_seconds=refresh_remaining_seconds,
            next_refresh_available_at=feed_state.next_refresh_available_at,
            refresh_interval_seconds=max(0, refresh_interval_seconds),
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
    current_user: User | None = None,
    category_key: str | None = None,
) -> StrangerProfileResponse | None:
    """
    Get stranger profile by qiao_id.

    This is a public endpoint that returns basic persona metadata.
    """
    try:
        visible_review_scopes = resolve_visible_review_scopes(current_user)
        require_minor_visible = is_minor_mode_enabled(current_user)
        (
            persona,
            profile,
            valid_category_key,
            category_title,
        ) = await discovery_data.get_persona_profile_by_qiao_id(
            db=db,
            qiao_id=qiao_id,
            category_key=category_key,
            visible_review_scopes=visible_review_scopes,
            require_minor_visible=require_minor_visible,
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

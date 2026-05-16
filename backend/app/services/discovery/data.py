"""Discovery data layer."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
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
from app.models.content import SquareCategory, SquareTypeEntry, SquareUserCategoryState
from app.models.profile import Profile
from app.type_defs import JSONValue
from app.utils.logging import get_logger

logger = get_logger(__name__)

_CURSOR_SCHEMA_VERSION = 1


@dataclass(slots=True)
class SquareFeedRecord:
    qiao_id: str
    type_id: int
    tags_payload: JSONValue | None
    remark: str | None
    nickname: str | None
    gender: int | None
    bio: str | None
    region: str | None
    avatar_key: str | None
    type_rank: int
    sort_key: str


@dataclass(slots=True)
class SquareFeedMetrics:
    candidate_count: int
    excluded_history_count: int
    duplicate_filtered_count: int
    query_duration_ms: int


@dataclass(slots=True)
class SquareFeedPage:
    records: list[SquareFeedRecord]
    has_more: bool
    next_cursor: str | None
    metrics: SquareFeedMetrics


@dataclass(slots=True)
class SquareCategoryFeedState:
    feed_version: str
    last_refreshed_at: datetime
    next_refresh_available_at: datetime


@dataclass(slots=True)
class _DecodedCursor:
    page_index: int
    type_rank: int
    sort_key: str
    qiao_id: str


def _encode_square_cursor(*, feed_version: str, page_index: int, record: SquareFeedRecord) -> str:
    payload = {
        "v": _CURSOR_SCHEMA_VERSION,
        "f": feed_version,
        "p": page_index,
        "t": record.type_rank,
        "s": record.sort_key,
        "q": record.qiao_id,
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_square_cursor(cursor: str, *, feed_version: str) -> _DecodedCursor:
    normalized = cursor.strip()
    if not normalized:
        raise ValueError("INVALID_CURSOR")

    padding = "=" * (-len(normalized) % 4)
    try:
        decoded = base64.urlsafe_b64decode(f"{normalized}{padding}".encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("INVALID_CURSOR") from exc

    payload_map = payload if isinstance(payload, dict) else {}
    if payload_map.get("v") != _CURSOR_SCHEMA_VERSION:
        raise ValueError("INVALID_CURSOR")
    if payload_map.get("f") != feed_version:
        raise ValueError("INVALID_CURSOR")

    page_index = payload_map.get("p")
    type_rank = payload_map.get("t")
    sort_key = payload_map.get("s")
    qiao_id = payload_map.get("q")
    if not isinstance(page_index, int) or page_index <= 0:
        raise ValueError("INVALID_CURSOR")
    if not isinstance(type_rank, int) or type_rank <= 0:
        raise ValueError("INVALID_CURSOR")
    if not isinstance(sort_key, str) or not sort_key:
        raise ValueError("INVALID_CURSOR")
    if not isinstance(qiao_id, str) or not qiao_id:
        raise ValueError("INVALID_CURSOR")
    return _DecodedCursor(
        page_index=page_index,
        type_rank=type_rank,
        sort_key=sort_key,
        qiao_id=qiao_id,
    )


def resolve_square_next_page_index(*, cursor: str | None, feed_version: str) -> int:
    """Resolve next page index from cursor for a given feed."""

    if cursor is None:
        return 1
    decoded = _decode_square_cursor(cursor, feed_version=feed_version)
    return decoded.page_index + 1


async def get_active_square_categories(
    db: AsyncSession,
    *,
    visible_review_scopes: tuple[int, ...] | None = None,
    require_minor_visible: bool = False,
) -> list[SquareCategory]:
    """Load active categories."""

    conditions = [
        SquareCategory.status == SquareCategoryStatus.ACTIVE,
        SquareCategory.theme_key.in_(SQUARE_CATEGORY_THEME_KEYS),
    ]
    if visible_review_scopes:
        conditions.append(SquareCategory.review_visibility_scope.in_(visible_review_scopes))
    if require_minor_visible:
        conditions.append(SquareCategory.minor_visible.is_(True))

    stmt = (
        select(SquareCategory)
        .where(*conditions)
        .order_by(
            SquareCategory.sort_order.asc(),
            SquareCategory.category_key.asc(),
        )
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_square_feed_page(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    category_key: str,
    feed_version: str,
    current_page_index: int,
    cursor: str | None,
    page_size: int,
) -> SquareFeedPage:
    """Load a deterministic random feed page for discovery square."""

    started_at = time.perf_counter()

    limit = max(1, page_size)
    active_type_ids_result = await db.execute(
        select(SquareTypeEntry.type_id)
        .where(
            SquareTypeEntry.status == SquareEntryStatus.ACTIVE,
            SquareTypeEntry.category_key == category_key,
        )
        .distinct()
    )
    active_type_ids = [int(type_id) for type_id in active_type_ids_result.scalars().all()]
    if not active_type_ids:
        metrics = SquareFeedMetrics(
            candidate_count=0,
            excluded_history_count=0,
            duplicate_filtered_count=0,
            query_duration_ms=int((time.perf_counter() - started_at) * 1000),
        )
        return SquareFeedPage(records=[], has_more=False, next_cursor=None, metrics=metrics)

    excluded_history_count_result = await db.execute(
        select(func.count(func.distinct(Contact.contact_qiao_id))).where(
            Contact.user_qiao_id == user_qiao_id,
            Contact.contact_type == ContactType.AI,
        )
    )
    excluded_history_count = int(excluded_history_count_result.scalar() or 0)

    excluded_contacts_subquery = (
        select(Contact.contact_qiao_id)
        .where(
            Contact.user_qiao_id == user_qiao_id,
            Contact.contact_type == ContactType.AI,
        )
        .distinct()
        .subquery()
    )

    base_filters = [
        AIPersona.status == AIPersonaStatus.ACTIVE,
        AIPersona.type_id.in_(active_type_ids),
        ~AIPersona.qiao_id.in_(select(excluded_contacts_subquery.c.contact_qiao_id)),
    ]
    profile_join_conditions = and_(
        Profile.owner_qiao_id == AIPersona.qiao_id,
        Profile.owner_type == ProfileOwnerType.AI_PERSONA,
    )

    candidate_count_result = await db.execute(
        select(func.count())
        .select_from(AIPersona)
        .join(Profile, profile_join_conditions)
        .where(and_(*base_filters))
    )
    candidate_count = int(candidate_count_result.scalar() or 0)
    if candidate_count <= 0:
        metrics = SquareFeedMetrics(
            candidate_count=0,
            excluded_history_count=excluded_history_count,
            duplicate_filtered_count=0,
            query_duration_ms=int((time.perf_counter() - started_at) * 1000),
        )
        return SquareFeedPage(records=[], has_more=False, next_cursor=None, metrics=metrics)

    decoded_cursor: _DecodedCursor | None = None
    if cursor:
        decoded_cursor = _decode_square_cursor(cursor, feed_version=feed_version)

    seed_prefix = f"{user_qiao_id}:{category_key}:{feed_version}"
    sort_key_expr = func.md5(func.concat(seed_prefix, ":", AIPersona.qiao_id))
    type_rank_expr = func.row_number().over(
        partition_by=AIPersona.type_id,
        order_by=(sort_key_expr.asc(), AIPersona.qiao_id.asc()),
    )
    candidate_subquery = (
        select(
            AIPersona.qiao_id.label("qiao_id"),
            AIPersona.type_id.label("type_id"),
            AIPersona.tags.label("tags_payload"),
            AIPersona.remark.label("remark"),
            Profile.nickname.label("nickname"),
            Profile.gender.label("gender"),
            Profile.bio.label("bio"),
            Profile.region.label("region"),
            Profile.avatar_key.label("avatar_key"),
            sort_key_expr.label("sort_key"),
            type_rank_expr.label("type_rank"),
        )
        .join(Profile, profile_join_conditions)
        .where(and_(*base_filters))
        .subquery()
    )

    feed_query = select(candidate_subquery).order_by(
        candidate_subquery.c.type_rank.asc(),
        candidate_subquery.c.sort_key.asc(),
        candidate_subquery.c.qiao_id.asc(),
    )
    if decoded_cursor is not None:
        feed_query = feed_query.where(
            or_(
                candidate_subquery.c.type_rank > decoded_cursor.type_rank,
                and_(
                    candidate_subquery.c.type_rank == decoded_cursor.type_rank,
                    candidate_subquery.c.sort_key > decoded_cursor.sort_key,
                ),
                and_(
                    candidate_subquery.c.type_rank == decoded_cursor.type_rank,
                    candidate_subquery.c.sort_key == decoded_cursor.sort_key,
                    candidate_subquery.c.qiao_id > decoded_cursor.qiao_id,
                ),
            )
        )
    feed_query = feed_query.limit(limit + 1)

    feed_rows_result = await db.execute(feed_query)
    feed_rows = list(feed_rows_result.mappings().all())

    has_more = len(feed_rows) > limit
    page_rows = feed_rows[:limit]

    records: list[SquareFeedRecord] = []
    seen_qiao_ids: set[str] = set()
    duplicate_filtered_count = 0
    for row in page_rows:
        qiao_id = str(row["qiao_id"])
        if qiao_id in seen_qiao_ids:
            duplicate_filtered_count += 1
            continue
        seen_qiao_ids.add(qiao_id)
        records.append(
            SquareFeedRecord(
                qiao_id=qiao_id,
                type_id=int(row["type_id"]),
                tags_payload=row["tags_payload"],
                remark=row["remark"],
                nickname=row["nickname"],
                gender=row["gender"],
                bio=row["bio"],
                region=row["region"],
                avatar_key=row["avatar_key"],
                type_rank=int(row["type_rank"]),
                sort_key=str(row["sort_key"]),
            )
        )

    next_cursor = None
    if has_more and records:
        next_cursor = _encode_square_cursor(
            feed_version=feed_version,
            page_index=current_page_index,
            record=records[-1],
        )

    metrics = SquareFeedMetrics(
        candidate_count=candidate_count,
        excluded_history_count=excluded_history_count,
        duplicate_filtered_count=duplicate_filtered_count,
        query_duration_ms=int((time.perf_counter() - started_at) * 1000),
    )

    return SquareFeedPage(
        records=records,
        has_more=has_more,
        next_cursor=next_cursor,
        metrics=metrics,
    )


def build_square_feed_version(*, now: datetime | None = None) -> str:
    """Build feed version identifier from UTC timestamp."""

    ts = now or datetime.now(UTC)
    return ts.strftime("%Y%m%d%H%M%S%f")


async def get_or_refresh_square_feed_state(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    category_key: str,
    refresh_interval_seconds: int,
) -> SquareCategoryFeedState:
    """Load user-category feed state and rotate feed when refresh window expires."""

    now = datetime.now(UTC)
    interval_seconds = max(0, refresh_interval_seconds)
    next_refresh_at = now + timedelta(seconds=interval_seconds)

    stmt = (
        select(SquareUserCategoryState)
        .where(
            SquareUserCategoryState.user_qiao_id == user_qiao_id,
            SquareUserCategoryState.category_key == category_key,
        )
        .limit(1)
        .with_for_update()
    )
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()

    if state is None:
        state = SquareUserCategoryState(
            user_qiao_id=user_qiao_id,
            category_key=category_key,
            feed_version=build_square_feed_version(now=now),
            last_refreshed_at=now,
            next_refresh_available_at=next_refresh_at,
        )
        db.add(state)
        await db.flush()
        return SquareCategoryFeedState(
            feed_version=state.feed_version,
            last_refreshed_at=state.last_refreshed_at,
            next_refresh_available_at=state.next_refresh_available_at,
        )

    if state.next_refresh_available_at <= now:
        state.feed_version = build_square_feed_version(now=now)
        state.last_refreshed_at = now
        state.next_refresh_available_at = next_refresh_at
        db.add(state)
        await db.flush()

    return SquareCategoryFeedState(
        feed_version=state.feed_version,
        last_refreshed_at=state.last_refreshed_at,
        next_refresh_available_at=state.next_refresh_available_at,
    )


async def get_square_feed_state(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    category_key: str,
) -> SquareCategoryFeedState | None:
    """Load persisted user-category feed state without rotating feed version."""

    stmt = (
        select(SquareUserCategoryState)
        .where(
            SquareUserCategoryState.user_qiao_id == user_qiao_id,
            SquareUserCategoryState.category_key == category_key,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()
    if state is None:
        return None
    return SquareCategoryFeedState(
        feed_version=state.feed_version,
        last_refreshed_at=state.last_refreshed_at,
        next_refresh_available_at=state.next_refresh_available_at,
    )


async def get_persona_profile_by_qiao_id(
    db: AsyncSession,
    *,
    qiao_id: str,
    category_key: str | None = None,
    visible_review_scopes: tuple[int, ...] | None = None,
    require_minor_visible: bool = False,
) -> tuple[AIPersona | None, Profile | None, str | None, str | None]:
    """Load the AI persona profile and validate optional category context."""

    try:
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
                AIPersona.qiao_id == qiao_id,
                AIPersona.status == AIPersonaStatus.ACTIVE,
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        row = result.first()
        if row is None:
            return None, None, None, None
        persona, profile = row

        if category_key is None:
            return persona, profile, None, None

        category_stmt = (
            select(SquareCategory.category_key, SquareCategory.title)
            .where(
                SquareCategory.category_key == category_key,
                SquareCategory.status == SquareCategoryStatus.ACTIVE,
                SquareCategory.theme_key.in_(SQUARE_CATEGORY_THEME_KEYS),
            )
            .limit(1)
        )
        if visible_review_scopes:
            category_stmt = category_stmt.where(
                SquareCategory.review_visibility_scope.in_(visible_review_scopes)
            )
        if require_minor_visible:
            category_stmt = category_stmt.where(SquareCategory.minor_visible.is_(True))
        category_result = await db.execute(category_stmt)
        category_row = category_result.first()
        if category_row is None:
            return persona, profile, None, None
        return persona, profile, category_row[0], category_row[1]
    except Exception as exc:
        logger.error(
            "fetch_persona_profile_failed",
            qiao_id=qiao_id,
            category_key=category_key,
            error=str(exc),
        )
        raise

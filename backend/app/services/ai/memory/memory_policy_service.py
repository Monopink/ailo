"""Unified memory policy service for write-time governance."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai.instance import AIInstance
from app.models.ai.memory import AIInstanceMemory
from app.services.ai.memory.config import (
    get_memory_budget_tokens_for_params,
    get_memory_limits_for_params,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

MIN_IMPORTANCE = 1
MAX_IMPORTANCE = 10
MAX_RECENT_REFRESH_COOLDOWN_HOURS = 12
RECENT_HALF_LIFE_DAYS = 3.0
REFRESH_REWARD_DECAY = 0.7
CORE_SOURCE_STRENGTH_THRESHOLD = 4
MIN_NEAR_DUP_CONTENT_LENGTH = 8
LLM_CORE_REMOVE_MAX_SOURCE_STRENGTH = 3

ORIGIN_ADMIN = "admin"
ORIGIN_TEMPLATE = "template"
ORIGIN_LLM = "llm"
ORIGIN_STRUCTURED = "structured"

_CONFLICT_OVERRIDE_MARK = 1

_SHORT_TERM_TERMS = (
    "今天",
    "明天",
    "这周",
    "下周",
    "最近",
    "刚刚",
    "正在",
    "计划",
    "打算",
)

_CITY_PATTERNS = (
    re.compile(r"(?:我住在|我现在住在|我在)([\u4e00-\u9fa5A-Za-z]{2,16})(?:市|区|县)?"),
    re.compile(r"(?:居住地是|家在)([\u4e00-\u9fa5A-Za-z]{2,16})(?:市|区|县)?"),
)
_OCCUPATION_PATTERNS = (
    re.compile(r"(?:我的职业是|我是)([^，。；,;]{2,20})"),
    re.compile(r"(?:我从事)([^，。；,;]{2,20})"),
)
_PREFERENCE_PATTERNS = (
    re.compile(r"(?:我喜欢)([^，。；,;]{1,20})"),
    re.compile(r"(?:我不喜欢|我讨厌)([^，。；,;]{1,20})"),
)


def normalize_memory_content(content: str) -> str:
    """Normalize memory content for deterministic dedup comparisons."""

    compact = " ".join(content.strip().split())
    return (
        compact.replace("，", ",")
        .replace("。", ".")
        .replace("；", ";")
        .replace("：", ":")
        .replace("（", "(")
        .replace("）", ")")
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )


def source_strength_for_origin(origin: str) -> int:
    """Map write origin to source strength rank."""

    if origin == ORIGIN_ADMIN:
        return 5
    if origin == ORIGIN_STRUCTURED:
        return 4
    if origin in {ORIGIN_TEMPLATE, ORIGIN_LLM}:
        return 2
    return 1


def infer_fact_key(content: str) -> str | None:
    """Infer conservative fact_key only for fixed high-value slots."""

    text = normalize_memory_content(content)
    if not text:
        return None

    fact_key: str | None = None

    for pattern in _CITY_PATTERNS:
        match = pattern.search(text)
        if match:
            city = match.group(1)
            fact_key = f"profile.residence_city:{city.lower()}"
            break

    if fact_key is None:
        for pattern in _OCCUPATION_PATTERNS:
            match = pattern.search(text)
            if match:
                occupation = match.group(1)
                fact_key = f"profile.occupation:{occupation.lower()}"
                break

    if fact_key is None:
        if "已婚" in text or "结婚" in text:
            fact_key = "relationship.partner_status:married"
        elif "恋爱" in text or "对象" in text:
            fact_key = "relationship.partner_status:in_relationship"
        elif "单身" in text:
            fact_key = "relationship.partner_status:single"

    if fact_key is None:
        for pattern in _PREFERENCE_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            item = match.group(1).lower()
            sentiment = "like" if "喜欢" in text and "不喜欢" not in text else "dislike"
            fact_key = f"preference.long_term:{sentiment}:{item}"
            break

    return fact_key


def compute_recent_utility(memory: AIInstanceMemory, now: datetime) -> float:
    """Compute utility score for ranking recent memories."""

    anchor_time = (
        memory.last_reinforced_at
        or memory.refreshed_at
        or memory.updated_at
        or memory.created_at
        or now
    )
    age_days = max((now - anchor_time).total_seconds() / 86400.0, 0.0)
    freshness = math.exp(-math.log(2) * age_days / RECENT_HALF_LIFE_DAYS)
    importance_norm = max(min(int(memory.importance), 10), 1) / 10.0
    source_norm = max(min(int(memory.source_strength), 5), 1) / 5.0

    reinforce_factor = math.pow(REFRESH_REWARD_DECAY, max(int(memory.reinforce_count), 0))
    adjusted_freshness = min(1.0, freshness + (1.0 - reinforce_factor) * 0.2)

    return 0.45 * adjusted_freshness + 0.35 * importance_norm + 0.20 * source_norm


def estimate_memory_tokens(content: str) -> int:
    """Estimate token usage for budgeting heuristics."""

    normalized = normalize_memory_content(content)
    if not normalized:
        return 1
    return max(1, math.ceil(len(normalized) / 2))


def should_downgrade_core(content: str, source_strength: int) -> bool:
    """Check whether a core candidate should be downgraded to recent."""

    normalized = normalize_memory_content(content)
    if any(term in normalized for term in _SHORT_TERM_TERMS):
        return True
    return source_strength < CORE_SOURCE_STRENGTH_THRESHOLD


async def lock_instance_for_memory_write(db: AsyncSession, instance_id: int) -> AIInstance:
    """Lock AI instance row for serialized memory write operations."""

    stmt = select(AIInstance).where(AIInstance.id == instance_id).with_for_update()
    result = await db.execute(stmt)
    instance = result.scalar_one_or_none()
    if instance is None:
        raise ValueError(f"Instance not found for memory write: {instance_id}")
    return instance


async def _find_active_by_normalized_content(
    db: AsyncSession,
    *,
    instance_id: int,
    normalized_content: str,
) -> AIInstanceMemory | None:
    stmt = (
        select(AIInstanceMemory)
        .where(
            AIInstanceMemory.instance_id == instance_id,
            AIInstanceMemory.status == 1,
            AIInstanceMemory.normalized_content == normalized_content,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _find_similar_recent_candidate(
    db: AsyncSession,
    *,
    instance_id: int,
    normalized_content: str,
    threshold: float,
) -> AIInstanceMemory | None:
    if len(normalized_content) < MIN_NEAR_DUP_CONTENT_LENGTH:
        return None

    similarity_score = func.similarity(AIInstanceMemory.normalized_content, normalized_content)
    stmt = (
        select(AIInstanceMemory)
        .where(
            AIInstanceMemory.instance_id == instance_id,
            AIInstanceMemory.status == 1,
            AIInstanceMemory.memory_type == "recent",
            AIInstanceMemory.normalized_content.is_not(None),
            similarity_score >= threshold,
        )
        .order_by(similarity_score.desc(), AIInstanceMemory.updated_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _find_active_by_fact_key(
    db: AsyncSession,
    *,
    instance_id: int,
    fact_key: str,
    memory_type: str,
) -> AIInstanceMemory | None:
    stmt = (
        select(AIInstanceMemory)
        .where(
            AIInstanceMemory.instance_id == instance_id,
            AIInstanceMemory.status == 1,
            AIInstanceMemory.fact_key == fact_key,
            AIInstanceMemory.memory_type == memory_type,
        )
        .order_by(
            AIInstanceMemory.source_strength.desc(),
            AIInstanceMemory.updated_at.desc(),
            AIInstanceMemory.id.desc(),
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _merge_into_existing_memory(
    memory: AIInstanceMemory,
    *,
    source_strength: int,
    importance: int,
    source_message_id: int | None,
    now: datetime,
) -> None:
    memory.reinforce_count = int(memory.reinforce_count) + 1
    memory.last_reinforced_at = now
    memory.updated_at = now
    memory.importance = max(int(memory.importance), int(importance))
    memory.source_strength = max(int(memory.source_strength), int(source_strength))
    if source_message_id is not None:
        memory.source_message_id = source_message_id


async def upsert_memory_with_policy(
    db: AsyncSession,
    *,
    instance: AIInstance,
    memory_type: str,
    content: str,
    importance: int,
    origin: str,
    source_message_id: int | None,
    source_strength_override: int | None = None,
    dedup_similarity_threshold: float = 0.90,
) -> tuple[AIInstanceMemory | None, bool]:
    """Apply policy-driven upsert and return memory plus downgrade flag."""

    if memory_type not in {"core", "recent"}:
        return None, False

    normalized_content = normalize_memory_content(content)
    if not normalized_content:
        return None, False

    importance_int = max(min(int(importance), MAX_IMPORTANCE), MIN_IMPORTANCE)
    source_strength = (
        source_strength_override
        if source_strength_override is not None
        else source_strength_for_origin(origin)
    )
    source_strength = max(min(int(source_strength), 5), 1)

    target_type = memory_type
    downgraded = False
    if target_type == "core" and should_downgrade_core(content, source_strength):
        target_type = "recent"
        downgraded = True

    fact_key = infer_fact_key(normalized_content)
    now = datetime.now(UTC)

    exact_match = await _find_active_by_normalized_content(
        db,
        instance_id=instance.id,
        normalized_content=normalized_content,
    )
    if exact_match is not None:
        _merge_into_existing_memory(
            exact_match,
            source_strength=source_strength,
            importance=importance_int,
            source_message_id=source_message_id,
            now=now,
        )
        if fact_key and not exact_match.fact_key:
            exact_match.fact_key = fact_key
        if target_type == "core" and source_strength >= int(exact_match.source_strength):
            exact_match.memory_type = "core"
            exact_match.expires_at = None
        return exact_match, downgraded

    if target_type == "recent":
        similar_recent = await _find_similar_recent_candidate(
            db,
            instance_id=instance.id,
            normalized_content=normalized_content,
            threshold=dedup_similarity_threshold,
        )
        if similar_recent is not None:
            _merge_into_existing_memory(
                similar_recent,
                source_strength=source_strength,
                importance=importance_int,
                source_message_id=source_message_id,
                now=now,
            )
            if fact_key and not similar_recent.fact_key:
                similar_recent.fact_key = fact_key
            logger.info(
                "memory_dedup_merge_count",
                instance_id=instance.id,
                memory_id=similar_recent.id,
                dedup_type="near",
            )
            return similar_recent, downgraded

    if fact_key:
        conflict_candidate = await _find_active_by_fact_key(
            db,
            instance_id=instance.id,
            fact_key=fact_key,
            memory_type=target_type,
        )
        if (
            conflict_candidate is not None
            and conflict_candidate.normalized_content != normalized_content
        ):
            logger.info(
                "memory_conflict_detect_count",
                instance_id=instance.id,
                memory_id=conflict_candidate.id,
                fact_key=fact_key,
            )
            existing_strength = int(conflict_candidate.source_strength)
            if source_strength >= existing_strength:
                conflict_candidate.content = content
                conflict_candidate.normalized_content = normalized_content
                conflict_candidate.importance = importance_int
                conflict_candidate.source_strength = source_strength
                conflict_candidate.fact_key = fact_key
                conflict_candidate.conflict_flag = _CONFLICT_OVERRIDE_MARK
                conflict_candidate.reinforce_count = int(conflict_candidate.reinforce_count) + 1
                conflict_candidate.last_reinforced_at = now
                conflict_candidate.updated_at = now
                if source_message_id is not None:
                    conflict_candidate.source_message_id = source_message_id
                if target_type == "core":
                    conflict_candidate.expires_at = None
                logger.info(
                    "memory_conflict_override_count",
                    instance_id=instance.id,
                    memory_id=conflict_candidate.id,
                    fact_key=fact_key,
                )
                return conflict_candidate, downgraded
            if target_type == "core":
                target_type = "recent"
                downgraded = True

    new_memory = AIInstanceMemory(
        instance_id=instance.id,
        instance_qiao_id=instance.qiao_id,
        user_id=instance.user_id,
        user_qiao_id=instance.user_qiao_id,
        memory_type=target_type,
        content=content,
        normalized_content=normalized_content,
        importance=importance_int,
        reinforce_count=0,
        last_reinforced_at=None,
        source_strength=source_strength,
        fact_key=fact_key,
        status=1,
        source_message_id=source_message_id,
    )
    if target_type == "core":
        new_memory.expires_at = None
    db.add(new_memory)
    return new_memory, downgraded


async def remove_memory_by_content_with_policy(
    db: AsyncSession,
    *,
    instance_id: int,
    content: str,
    origin: str,
) -> bool:
    """Archive matched active memory by content with source-strength guard."""

    normalized = normalize_memory_content(content)
    if not normalized:
        return False

    stmt = (
        select(AIInstanceMemory)
        .where(
            AIInstanceMemory.instance_id == instance_id,
            AIInstanceMemory.status == 1,
            AIInstanceMemory.normalized_content == normalized,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()
    if memory is None:
        return False

    source_strength = source_strength_for_origin(origin)
    if memory.memory_type == "core" and source_strength <= LLM_CORE_REMOVE_MAX_SOURCE_STRENGTH:
        logger.warning(
            "memory_core_remove_blocked",
            instance_id=instance_id,
            memory_id=memory.id,
            origin=origin,
        )
        return False

    memory.status = 2
    memory.updated_at = datetime.now(UTC)
    return True


async def remove_memory_by_id_with_policy(
    db: AsyncSession,
    *,
    instance_id: int,
    memory_id: int,
    origin: str,
) -> bool:
    """Archive matched active memory by id with source-strength guard."""

    stmt = (
        select(AIInstanceMemory)
        .where(
            AIInstanceMemory.instance_id == instance_id,
            AIInstanceMemory.id == memory_id,
            AIInstanceMemory.status == 1,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()
    if memory is None:
        return False

    source_strength = source_strength_for_origin(origin)
    if memory.memory_type == "core" and source_strength <= LLM_CORE_REMOVE_MAX_SOURCE_STRENGTH:
        logger.warning(
            "memory_core_remove_blocked",
            instance_id=instance_id,
            memory_id=memory.id,
            origin=origin,
        )
        return False

    memory.status = 2
    memory.updated_at = datetime.now(UTC)
    return True


async def update_memory_by_content_with_policy(
    db: AsyncSession,
    *,
    instance: AIInstance,
    old_content: str,
    new_content: str,
    new_importance: int | None,
    origin: str,
    source_message_id: int | None,
) -> bool:
    """Update memory content by archiving old record and re-upserting new content."""

    old_normalized = normalize_memory_content(old_content)
    if not old_normalized:
        return False

    stmt = (
        select(AIInstanceMemory)
        .where(
            AIInstanceMemory.instance_id == instance.id,
            AIInstanceMemory.status == 1,
            AIInstanceMemory.normalized_content == old_normalized,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()
    if memory is None:
        return False

    source_strength = source_strength_for_origin(origin)
    if source_strength < int(memory.source_strength):
        logger.warning(
            "memory_update_blocked_low_strength",
            instance_id=instance.id,
            memory_id=memory.id,
            origin=origin,
            source_strength=source_strength,
            existing_source_strength=memory.source_strength,
        )
        return False

    memory.status = 2
    memory.updated_at = datetime.now(UTC)

    importance = new_importance if new_importance is not None else int(memory.importance)
    await upsert_memory_with_policy(
        db,
        instance=instance,
        memory_type=memory.memory_type,
        content=new_content,
        importance=importance,
        origin=origin,
        source_message_id=source_message_id,
    )
    return True


async def refresh_recent_memories_with_policy(
    db: AsyncSession,
    *,
    instance_id: int,
    memory_ids: Sequence[int],
) -> tuple[list[int], list[int]]:
    """Refresh recent memories with cooldown and reinforcement updates."""

    now = datetime.now(UTC)
    hit_ids: list[int] = []
    miss_ids: list[int] = []

    for memory_id in memory_ids:
        stmt = (
            select(AIInstanceMemory)
            .where(
                AIInstanceMemory.instance_id == instance_id,
                AIInstanceMemory.id == int(memory_id),
                AIInstanceMemory.status == 1,
                AIInstanceMemory.memory_type == "recent",
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        memory = result.scalar_one_or_none()
        if memory is None:
            miss_ids.append(int(memory_id))
            continue

        last_reinforced_at = memory.last_reinforced_at
        if last_reinforced_at is not None:
            elapsed_hours = (now - last_reinforced_at).total_seconds() / 3600
            if elapsed_hours < MAX_RECENT_REFRESH_COOLDOWN_HOURS:
                logger.info(
                    "memory_refresh_cooldown_skipped",
                    instance_id=instance_id,
                    memory_id=memory.id,
                )
                hit_ids.append(int(memory_id))
                continue

        memory.refreshed_at = now
        memory.last_reinforced_at = now
        memory.reinforce_count = int(memory.reinforce_count) + 1
        memory.updated_at = now
        hit_ids.append(int(memory_id))

    return hit_ids, miss_ids


async def archive_recent_over_limit(
    db: AsyncSession,
    *,
    instance: AIInstance,
    trigger: str,
) -> int:
    """Archive low-utility recent memories when count/token budget is exceeded."""

    request_params = instance.request_params if isinstance(instance.request_params, Mapping) else {}
    limits = await get_memory_limits_for_params(
        db,
        request_params=request_params,
        llm_config_id=instance.llm_config_id,
    )
    budget_tokens = await get_memory_budget_tokens_for_params(
        db,
        request_params=request_params,
        llm_config_id=instance.llm_config_id,
    )

    stmt = select(AIInstanceMemory).where(
        AIInstanceMemory.instance_id == instance.id,
        AIInstanceMemory.status == 1,
        AIInstanceMemory.memory_type == "recent",
    )
    result = await db.execute(stmt)
    active_recent = list(result.scalars().all())
    if not active_recent:
        return 0

    now = datetime.now(UTC)
    ordered = sorted(
        active_recent,
        key=lambda item: (
            compute_recent_utility(item, now),
            int(item.importance),
            int(item.source_strength),
            int(item.reinforce_count),
            item.updated_at or item.created_at or now,
            int(item.id),
        ),
        reverse=True,
    )

    hard_limit_tokens = math.floor(float(budget_tokens) * 1.15)
    max_recent_count = int(limits.get("recent", 50))

    keep_ids: set[int] = set()
    token_total = 0
    for memory in ordered:
        if len(keep_ids) >= max_recent_count:
            break
        estimate = estimate_memory_tokens(memory.content)
        if token_total + estimate > hard_limit_tokens and keep_ids:
            continue
        keep_ids.add(int(memory.id))
        token_total += estimate

    if not keep_ids and ordered:
        keep_ids.add(int(ordered[0].id))

    archived_count = 0
    for memory in ordered:
        if int(memory.id) in keep_ids:
            continue
        memory.status = 2
        memory.updated_at = now
        archived_count += 1

    if archived_count > 0:
        logger.info(
            "memory_recent_archived_count",
            instance_id=instance.id,
            trigger=trigger,
            archived_count=archived_count,
            hard_limit_tokens=hard_limit_tokens,
            max_recent_count=max_recent_count,
        )

    return archived_count

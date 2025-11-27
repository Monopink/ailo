"""
Relationship selection helpers shared by business logic and admin tools.

Responsibilities:
- Collect relationship candidates for a given (style, dimension, position)
- Enforce limit_count based on instance-level relationship_counts
- Select final relationship using unified rules

All functions are stateless. DB access is restricted to candidate collection.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

logger = get_logger(__name__)


Candidate = Dict[str, Any]


async def collect_candidates(
    db: AsyncSession, *, style_id: int, dimension_id: int, position: int
) -> List[Candidate]:
    """
    Collect relationship candidates for one dimension given final position.

    Returns a list of candidates with priority, range, relationship info, and limit_count.
    """
    query = text(
        """
        SELECT DISTINCT
            drm.relationship_id,
            drm.priority,
            drm.start_position,
            drm.end_position,
            COALESCE(drm.limit_count, 0) AS limit_count,
            ar.display_name AS relationship_display_name,
            ar.prompt_fragment AS prompt_fragment
        FROM ai_dimension_relationship_mappings drm
        JOIN ai_relationships ar ON drm.relationship_id = ar.id
        JOIN ai_style_dimensions asd ON asd.dimension_id = drm.dimension_id
        WHERE asd.style_id = :style_id
          AND drm.dimension_id = :dimension_id
          AND drm.start_position <= :position
          AND drm.end_position >= :position
        ORDER BY drm.priority DESC
        """
    )
    result = await db.execute(
        query,
        {"style_id": int(style_id), "dimension_id": int(dimension_id), "position": int(position)},
    )
    rows = result.fetchall()
    candidates: List[Candidate] = []
    for r in rows:
        candidates.append(
            {
                "relationship_id": r.relationship_id,
                "relationship_display_name": r.relationship_display_name,
                "prompt_fragment": r.prompt_fragment,
                "priority": r.priority,
                "start_position": r.start_position,
                "end_position": r.end_position,
                "limit_count": r.limit_count,
            }
        )
    return candidates


def enforce_limit_count(
    candidates: List[Candidate], relationship_counts: Optional[Dict[str, Any]]
) -> List[Candidate]:
    """
    Filter candidates using limit_count and instance-level counts.

    - limit_count NULL/0 => unlimited
    - counts >= limit_count => drop
    - counts > limit_count => drop and log anomaly
    """
    if not relationship_counts:
        # No counts available (e.g., style test) => treat as 0
        return candidates

    filtered: List[Candidate] = []
    for c in candidates:
        rel_id = c.get("relationship_id")
        try:
            limit = int(c.get("limit_count") or 0)
        except Exception:
            limit = 0
        if limit <= 0:
            filtered.append(c)
            continue
        # counts may be stored with string keys in JSONB
        cnt = relationship_counts.get(str(rel_id))
        if cnt is None:
            cnt = relationship_counts.get(str(rel_id) if rel_id is not None else "", 0)
        try:
            cnt_int = int(cnt or 0)
        except Exception:
            cnt_int = 0

        if cnt_int > limit:
            logger.error(
                "relationship_count_anomaly_gt_limit",
                relationship_id=rel_id,
                count=cnt_int,
                limit=limit,
            )
            # drop
            continue

        if cnt_int >= limit:
            # reached limit
            continue

        filtered.append(c)
    return filtered


def select_final_relationship(
    candidates_across_dimensions: List[Candidate],
    *,
    higher_is_better: bool = True,
) -> Dict[str, Any]:
    """
    Select final relationship using unified rules.

    Rules:
    - Aggregate candidates by relationship_id with max priority
    - Pick single highest priority (max if higher_is_better)
    - If tie on top priority => return empty (None) with reason
    - If empty list => return empty (None) with reason

    Note: Per-dimension current relationship filtering should be applied before calling this function.
    """
    if not candidates_across_dimensions:
        return {"relationship": None, "changed": False, "reason": "no_candidate"}

    # Aggregate by relationship_id to compute max priority across dims
    agg: Dict[int, Dict[str, Any]] = {}
    for c in candidates_across_dimensions:
        rid_raw = c.get("relationship_id")
        pr_raw = c.get("priority")
        try:
            rid = int(rid_raw)
        except Exception:
            logger.error("candidate_missing_relationship_id", candidate=c)
            continue
        try:
            pr = int(pr_raw or 0)
        except Exception:
            pr = 0
        if rid not in agg:
            agg[rid] = {
                "relationship_id": rid,
                "relationship_display_name": c.get("relationship_display_name"),
                "prompt_fragment": c.get("prompt_fragment"),
                "max_priority": pr,
                "_sample": c,
            }
        else:
            if pr > agg[rid]["max_priority"]:
                agg[rid]["max_priority"] = pr

    if not agg:
        return {"relationship": None, "changed": False, "reason": "no_candidate"}

    # Determine top priority
    top_priority = (
        max(v["max_priority"] for v in agg.values())
        if higher_is_better
        else min(v["max_priority"] for v in agg.values())
    )
    top_relations = [v for v in agg.values() if v["max_priority"] == top_priority]

    if len(top_relations) > 1:
        logger.error("priority_tie_detected", top_priority=top_priority, candidates=len(top_relations))
        return {"relationship": None, "changed": False, "reason": "priority_tie"}

    selected = top_relations[0]
    # Use sampled candidate for prompt fragment consistency
    return {
        "relationship": selected.get("_sample"),
        "changed": True,
        "reason": "selected_highest_priority",
    }

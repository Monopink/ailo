"""
Admin instance relationship generation service.

Provides functionality for generating and previewing instance relationships
based on dimension scores and mapping algorithms.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.ai.instance_dimension import get_by_instance
from app.models.ai.instance import AIInstance
from app.models.ai.style import AIDimension, AIStyleDimension
from app.services.ai.queries import get_instance_context
from app.services.ai.relationship_scoring import (
    calculate_new_scores,
    update_instance_current_relationship,
    update_relationship_positions,
)
from app.services.ai.relationship_selection import collect_candidates, select_final_relationship
from app.services.ai.utils.position_mapping import map_score_to_position
from app.services.ai.utils.score_mapping import map_to_permille
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def generate_relationship_for_instance(
    db: AsyncSession,
    *,
    instance_id: int,
    overrides: dict[str, Any] | None = None,
    preview: bool = True,
) -> dict[str, Any]:
    """
    Generate relationship for an instance using current or overridden per-dimension inputs.

    - Uses JSON Schema min/max for mapping to [0,1000].
    - Applies per-dimension offset and collects candidates.
    - Applies per-dimension current relationship filtering.
    - Selects final relationship by priority (tie->empty).
    - preview=True -> does not persist; preview=False -> persist positions and current relationship.
    """
    # Load instance with style, personality and qiao_id
    result = await db.execute(
        select(AIInstance)
        .where(AIInstance.id == instance_id)
        .options(selectinload(AIInstance.style), selectinload(AIInstance.personality))
    )
    instance = result.scalar_one_or_none()
    if not instance:
        return {"success": False, "message": "Instance not found"}

    context = await get_instance_context(db, instance_id=instance_id)
    if not context:
        return {"success": False, "message": "Instance context not found"}

    # Load dimensions for style
    dims_result = await db.execute(
        select(AIDimension, AIStyleDimension.initial_position)
        .join(AIStyleDimension, AIStyleDimension.dimension_id == AIDimension.id)
        .where(AIStyleDimension.style_id == instance.style_id)
        .order_by(AIDimension.name)
    )
    style_dims = [
        type(
            "_Tmp",
            (),
            {
                "id": dim.id,
                "name": dim.name,
                "display_name": dim.display_name,
                "initial_position": init_pos,
            },
        )
        for dim, init_pos in dims_result.all()
    ]
    if not style_dims:
        return {"success": False, "message": "No dimensions configured for this style"}

    # Read JSON Schema for mapping ranges from personality
    json_schema = instance.personality.json_schema or {}
    score_props = json_schema.get("properties", {}).get("score", {}).get("properties", {})

    # Read current instance dimensions
    char_scores = await get_by_instance(db, instance_id)
    score_map = {row["dimension_id"]: row for row in char_scores} if char_scores else {}

    # Build override map for quick lookup by dimension_id
    override_map: dict[int, dict[str, Any]] = {}
    if overrides and isinstance(overrides.get("dimensions"), list):
        for d in overrides["dimensions"]:
            try:
                override_map[int(d.get("dimension_id"))] = d
            except Exception:
                continue

    # Process per-dimension mapping+offset and collect candidates
    dimension_results: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []

    for dim in style_dims:
        ov = override_map.get(dim.id, {})
        # Score: override -> current -> fallback 500
        score = ov.get("score")
        if score is None:
            base = score_map.get(dim.id, {})
            score = base.get("score", 500)
        try:
            score = float(score)
        except Exception:
            score = 500.0

        # Algorithm & params: override -> current -> defaults
        algorithm = ov.get("position_mapping_algorithm")
        if algorithm is None:
            base = score_map.get(dim.id, {})
            algorithm = base.get("position_mapping_algorithm", 1)
        try:
            algorithm = int(algorithm)
        except Exception:
            algorithm = 1

        params = ov.get("position_mapping_params") or {}
        if not params:
            base = score_map.get(dim.id, {})
            params = base.get("position_mapping_params", {}) or {}

        # Map using JSON Schema ranges (fallback 0..1000)
        dim_schema = score_props.get(dim.name, {}) if isinstance(score_props, dict) else {}
        min_v = dim_schema.get("minimum", 0)
        max_v = dim_schema.get("maximum", 1000)
        try:
            mapped = map_to_permille(score, float(min_v), float(max_v))
        except Exception as e:
            logger.error(
                "instance_generate_mapping_failed",
                instance_id=instance_id,
                dimension=dim.name,
                error=str(e),
            )
            return {"success": False, "message": f"Mapping failed for {dim.display_name}"}

        # Apply offset
        final_pos = map_score_to_position(
            algorithm=algorithm,
            score=float(mapped),
            initial_position=dim.initial_position,
            params=params,
        )

        # half-up rounding to int
        mapped_i = max(0, min(1000, int(float(mapped) + 0.5)))
        final_i = max(0, min(1000, int(float(final_pos) + 0.5)))

        # Collect candidates
        candidates = await collect_candidates(
            db, style_id=int(instance.style_id), dimension_id=int(dim.id), position=final_i
        )

        # Per-dimension current relationship filtering
        current_rel_id = getattr(instance, "relationship_id", None)
        if current_rel_id is not None and candidates:
            current_in_candidates = any(
                int(c.get("relationship_id")) == int(current_rel_id) for c in candidates
            )
            if current_in_candidates:
                candidates = [
                    c for c in candidates if int(c.get("relationship_id")) == int(current_rel_id)
                ]

        all_candidates.extend(candidates)

        dimension_results.append(
            {
                "dimension_id": dim.id,
                "dimension_name": dim.name,
                "dimension_display_name": dim.display_name,
                "input_score": score,
                "score_min": min_v,
                "score_max": max_v,
                "mapped_position": mapped_i,
                "initial_position": dim.initial_position,
                "algorithm": algorithm,
                "parameters": params,
                "final_position": final_i,
                "offset": final_i - mapped_i,
                "candidates": candidates,
            }
        )

    # Final selection
    selection = select_final_relationship(all_candidates, higher_is_better=True)
    selected = selection.get("relationship")
    reason = selection.get("reason")

    # Persist (optional): positions and current relationship
    if not preview:
        try:
            # Use overrides.score as llm_response_scores; calculate_new_scores will map via schema again
            llm_scores = {dr["dimension_name"]: int(dr["input_score"]) for dr in dimension_results}
            new_scores = await calculate_new_scores(db, context, llm_scores)
            await update_relationship_positions(db, instance_id, new_scores)
            if selected:
                disp = selected.get("relationship_display_name") or str(
                    selected.get("relationship_id") or ""
                )
                await update_instance_current_relationship(
                    db, instance_id, int(selected.get("relationship_id")), disp
                )
        except Exception as e:
            logger.error("instance_generate_persist_failed", instance_id=instance_id, error=str(e))
            return {"success": False, "message": f"Persist failed: {e!s}"}

    return {
        "success": True,
        "dimension_results": dimension_results,
        "selected_relationship": selected,
        "selection_reason": reason,
    }

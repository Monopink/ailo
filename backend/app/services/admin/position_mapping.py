"""
Admin-facing position mapping and relationship selection helpers.

This module adapts the shared AI selection utilities for admin test views
and advanced edit flows. It returns rich debug structures expected by
admin templates while delegating core logic to shared services.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from services.ai.utils.score_mapping import map_to_permille
from services.ai.utils.position_mapping import map_score_to_position, validate_algorithm_params
from services.ai.relationship_selection import collect_candidates, select_final_relationship
from models.ai.style import AIDimension, AIStyleDimension
from utils.logging import get_logger

logger = get_logger(__name__)


async def run_style_score_test(
    db: AsyncSession, *, style_id: int, form_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute per-dimension mapping + offset + candidate selection for style test.

    Returns a structure compatible with admin template ai_style_test.html.
    """
    # Load style dimensions
    dims_q = text(
        """
        SELECT d.id AS id, d.name AS name, d.display_name AS display_name, asd.initial_position AS initial_position
        FROM ai_style_dimensions AS asd
        JOIN ai_dimensions AS d ON d.id = asd.dimension_id
        WHERE asd.style_id = :style_id
        ORDER BY d.name
        """
    )
    result = await db.execute(dims_q, {"style_id": int(style_id)})
    dims = result.fetchall()
    if not dims:
        return {"success": False, "message": "No dimensions configured for this style"}

    # current relationship id (optional)
    current_relationship_id: Optional[int] = None
    raw_current_rel = form_data.get("current_relationship")
    if raw_current_rel:
        try:
            current_relationship_id = int(raw_current_rel)
        except Exception:
            return {"success": False, "message": "Invalid current_relationship value"}

    dimension_results: List[Dict[str, Any]] = []
    all_candidates: List[Dict[str, Any]] = []

    for dim in dims:
        dim_name = dim.name
        dim_algo_key = f"algorithm_{dim_name}"
        try:
            algorithm = int(form_data.get(dim_algo_key, "1"))
        except Exception:
            return {"success": False, "message": f"Invalid algorithm for {dim.display_name}"}

        params: Dict[str, Any] = {}
        if algorithm == 2:
            try:
                lb_raw = form_data.get(f"left_bias_{dim_name}")
                rb_raw = form_data.get(f"right_bias_{dim_name}")
                if lb_raw is None or rb_raw is None:
                    raise ValueError("missing_bias")
                left_bias = int(str(lb_raw))
                right_bias = int(str(rb_raw))
            except Exception:
                return {"success": False, "message": f"Missing V1 parameters for {dim.display_name}"}
            params = {"left_bias": left_bias, "right_bias": right_bias}
            if not validate_algorithm_params(algorithm, params):
                return {"success": False, "message": f"Invalid V1 parameters for {dim.display_name}"}

        # Scores and ranges
        try:
            s_raw = form_data.get(f"score_{dim_name}")
            smin_raw = form_data.get(f"score_min_{dim_name}")
            smax_raw = form_data.get(f"score_max_{dim_name}")
            if s_raw is None or smin_raw is None or smax_raw is None:
                raise ValueError("missing_scores")
            score = float(str(s_raw))
            score_min = float(str(smin_raw))
            score_max = float(str(smax_raw))
        except Exception:
            return {"success": False, "message": f"Missing score fields for {dim.display_name}"}

        try:
            mapped = map_to_permille(score, score_min, score_max)
        except Exception as e:
            logger.error("admin_score_mapping_failed", dimension=dim_name, error=str(e))
            return {"success": False, "message": f"Mapping failed for {dim.display_name}"}

        # Apply offset
        final_position = map_score_to_position(
            algorithm=algorithm,
            score=float(mapped),
            initial_position=dim.initial_position,
            params=params,
        )

        # half-up rounding to integer for UI consistency
        mapped_i = max(0, min(1000, int(float(mapped) + 0.5)))
        final_i = max(0, min(1000, int(float(final_position) + 0.5)))

        # Collect candidates for this dimension
        candidates = await collect_candidates(
            db, style_id=int(style_id), dimension_id=int(dim.id), position=final_i
        )

        # Per-dimension current relationship filtering
        if current_relationship_id is not None and candidates:
            current_in_candidates = any(
                int(c.get("relationship_id")) == int(current_relationship_id) for c in candidates
            )
            if current_in_candidates:
                candidates = [c for c in candidates if int(c.get("relationship_id")) == int(current_relationship_id)]

        all_candidates.extend(candidates)

        dimension_results.append(
            {
                "dimension_name": dim_name,
                "dimension_display_name": dim.display_name,
                "input_score": score,
                "score_min": score_min,
                "score_max": score_max,
                "mapped_position": mapped_i,
                "initial_position": dim.initial_position,
                "algorithm": algorithm,
                "parameters": params,
                "final_position": final_i,
                "offset": final_i - mapped_i,
                "candidates": candidates,
            }
        )

    # Aggregate unique candidates (dedupe by relationship_id tracking max priority)
    # Build mapping from relationship_id to source dimension display names
    rel_to_dims: Dict[int, set] = {}
    for dr in dimension_results:
        dims_disp = dr.get("dimension_display_name")
        for c in dr.get("candidates", []) or []:
            try:
                rrid = int(c.get("relationship_id"))
            except Exception:
                continue
            if rrid not in rel_to_dims:
                rel_to_dims[rrid] = set()
            if dims_disp:
                rel_to_dims[rrid].add(str(dims_disp))

    unique: Dict[int, Dict[str, Any]] = {}
    for c in all_candidates:
        rid = int(c["relationship_id"])
        pr = int(c.get("priority", 0))
        if rid not in unique:
            unique[rid] = {
                "relationship_id": rid,
                "relationship_name": c.get("relationship_name"),
                "relationship_display_name": c.get("relationship_display_name"),
                "prompt_fragment": c.get("prompt_fragment"),
                "count": 0,
                "max_priority": pr,
                "dimension_display_names": sorted(list(rel_to_dims.get(rid, set())))
                if rel_to_dims.get(rid)
                else [],
            }
        unique[rid]["count"] += 1
        if pr > unique[rid]["max_priority"]:
            unique[rid]["max_priority"] = pr

    all_unique_candidates = list(unique.values())

    # Final selection (no limit_count in style test)
    selection = select_final_relationship(all_candidates, higher_is_better=True)
    selected_relationship = selection.get("relationship")
    reason = selection.get("reason")

    return {
        "success": True,
        "dimension_results": dimension_results,
        "all_unique_candidates": all_unique_candidates,
        "all_candidates": all_unique_candidates,  # keep legacy field for template compatibility
        "selected_relationship": selected_relationship,
        "selection_reason": reason,
        "current_relationship_id": current_relationship_id,
        "current_relationship_name": None,
    }


async def generate_relationship_for_character(
    db: AsyncSession,
    *,
    character_id: int,
    overrides: Optional[Dict[str, Any]] = None,
    preview: bool = True,
) -> Dict[str, Any]:
    """
    Generate relationship for a character using current or overridden per-dimension inputs.

    - Uses JSON Schema min/max for mapping to [0,1000].
    - Applies per-dimension offset and collects candidates.
    - Applies per-dimension current relationship filtering.
    - Selects final relationship by priority (tie->empty).
    - preview=True -> does not persist; preview=False -> persist positions and current relationship.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from models.ai.character import AICharacter
    from models.ai.style import AIStyleDimension
    from crud.ai.character_dimension import get_by_character
    from services.ai.prompt import get_response_schema
    from services.ai.relationship import (
        calculate_new_scores,
        update_relationship_positions,
        update_current_relationship,
        determine_relationship_type,
    )

    # Load character with style, personality and qiao_id
    result = await db.execute(
        select(AICharacter).where(AICharacter.id == character_id).options(
            selectinload(AICharacter.style),
            selectinload(AICharacter.personality)
        )
    )
    character = result.scalar_one_or_none()
    if not character:
        return {"success": False, "message": "Character not found"}

    # Load dimensions for style
    dims_result = await db.execute(
        select(AIDimension, AIStyleDimension.initial_position)
        .join(AIStyleDimension, AIStyleDimension.dimension_id == AIDimension.id)
        .where(AIStyleDimension.style_id == character.style_id)
        .order_by(AIDimension.name)
    )
    style_dims = [
        type("_Tmp", (), {"id": dim.id, "name": dim.name, "display_name": dim.display_name, "initial_position": init_pos})
        for dim, init_pos in dims_result.all()
    ]
    if not style_dims:
        return {"success": False, "message": "No dimensions configured for this style"}

    # Read JSON Schema for mapping ranges from personality
    json_schema = character.personality.json_schema or {}
    score_props = json_schema.get("properties", {}).get("score", {}).get("properties", {})

    # Read current character dimensions
    char_scores = await get_by_character(db, character_id)
    score_map = {row["dimension_id"]: row for row in char_scores} if char_scores else {}

    # Build override map for quick lookup by dimension_id
    override_map: Dict[int, Dict[str, Any]] = {}
    if overrides and isinstance(overrides.get("dimensions"), list):
        for d in overrides["dimensions"]:
            try:
                override_map[int(d.get("dimension_id"))] = d
            except Exception:
                continue

    # Process per-dimension mapping+offset and collect candidates
    dimension_results: List[Dict[str, Any]] = []
    all_candidates: List[Dict[str, Any]] = []

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
                "character_generate_mapping_failed",
                character_id=character_id,
                dimension=dim.name,
                error=str(e),
            )
            return {"success": False, "message": f"Mapping failed for {dim.display_name}"}

        # Apply offset
        final_pos = map_score_to_position(
            algorithm=algorithm, score=float(mapped), initial_position=dim.initial_position, params=params
        )

        # half-up rounding to int
        mapped_i = max(0, min(1000, int(float(mapped) + 0.5)))
        final_i = max(0, min(1000, int(float(final_pos) + 0.5)))

        # Collect candidates
        candidates = await collect_candidates(
            db, style_id=int(character.style_id), dimension_id=int(dim.id), position=final_i
        )

        # Per-dimension current relationship filtering
        current_rel_id = getattr(character, "relationship_id", None)
        if current_rel_id is not None and candidates:
            current_in_candidates = any(
                int(c.get("relationship_id")) == int(current_rel_id) for c in candidates
            )
            if current_in_candidates:
                candidates = [c for c in candidates if int(c.get("relationship_id")) == int(current_rel_id)]

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
        # Build llm-style score input from per-dimension mapped scores back to integers of final positions
        # Use calculate_new_scores to keep single-entry point (it maps and offsets again but stays consistent)
        try:
            # Use overrides.score as llm_response_scores; calculate_new_scores will map via schema again
            llm_scores = {dr["dimension_name"]: int(dr["input_score"]) for dr in dimension_results}
            character_info = {
                "character_id": character_id,
                "style_id": character.style_id,
                "character": character,
            }
            new_scores = await calculate_new_scores(db, character_info, llm_scores)
            await update_relationship_positions(db, character_id, new_scores)
            if selected:
                disp = selected.get("relationship_display_name") or selected.get("relationship_name") or ""
                await update_current_relationship(
                    db, character_id, int(selected.get("relationship_id")), disp
                )
        except Exception as e:
            logger.error("character_generate_persist_failed", character_id=character_id, error=str(e))
            return {"success": False, "message": f"Persist failed: {str(e)}"}

    return {
        "success": True,
        "dimension_results": dimension_results,
        "selected_relationship": selected,
        "selection_reason": reason,
    }

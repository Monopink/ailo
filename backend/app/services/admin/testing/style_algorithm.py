"""
Admin style algorithm testing service.

Provides testing functionality for AI style score mapping and relationship selection.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from services.ai.utils.score_mapping import map_to_permille
from services.ai.utils.position_mapping import (
    get_algorithm_param_specs,
    map_score_to_position,
    parse_algorithm_params,
)
from services.ai.relationship_selection import collect_candidates, select_final_relationship
from enums.common import PositionMappingAlgorithm
from utils.logging import get_logger

logger = get_logger(__name__)

V1_PARAM_SPECS = get_algorithm_param_specs(PositionMappingAlgorithm.V1.value).get(
    PositionMappingAlgorithm.V1.value, []
)


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
        if algorithm == PositionMappingAlgorithm.V1.value:
            raw_params: Dict[str, Any] = {}
            missing_fields: List[str] = []
            for spec in V1_PARAM_SPECS:
                field_key = f"{spec['name']}_{dim_name}"
                raw_value = form_data.get(field_key)
                if raw_value is None or str(raw_value).strip() == "":
                    missing_fields.append(spec["label"])
                    continue
                raw_params[spec["name"]] = raw_value

            if missing_fields:
                return {
                    "success": False,
                    "message": f"Missing V1 parameters ({', '.join(missing_fields)}) for {dim.display_name}",
                }

            try:
                params = parse_algorithm_params(PositionMappingAlgorithm.V1, raw_params)
            except ValueError as exc:
                return {"success": False, "message": f"Invalid V1 parameters for {dim.display_name}: {exc}"}

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
                candidates = [
                    c for c in candidates if int(c.get("relationship_id")) == int(current_relationship_id)
                ]

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
                "relationship_display_name": c.get("relationship_display_name"),
                "prompt_fragment": c.get("prompt_fragment"),
                "count": 0,
                "max_priority": pr,
                "dimension_display_names": (
                    sorted(list(rel_to_dims.get(rid, set()))) if rel_to_dims.get(rid) else []
                ),
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
    }

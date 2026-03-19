"""
Admin style algorithm testing service.

Provides testing functionality for AI style score mapping and relationship selection.
"""

from typing import Any, NoReturn

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.common import PositionMappingAlgorithm
from app.services.ai.relationship_selection import (
    collect_candidates,
    select_final_relationship,
)
from app.services.ai.utils.position_mapping import (
    get_algorithm_param_specs,
    map_score_to_position,
    parse_algorithm_params,
)
from app.services.ai.utils.score_mapping import map_to_permille
from app.type_defs import RelationshipCandidate
from app.utils.logging import get_logger

logger = get_logger(__name__)


class StyleTestError(Exception):
    """Raised when submitted form data is invalid for the style test."""


def _style_test_fail(message: str) -> NoReturn:
    """Raise a validation error that should flow back to the caller."""
    raise StyleTestError(message)


V1_PARAM_SPECS = get_algorithm_param_specs(PositionMappingAlgorithm.V1.value).get(
    PositionMappingAlgorithm.V1.value, []
)
V1_PARAM_LABELS_ZH = {
    "left_sensitivity": "左侧敏感度（%）",
    "right_sensitivity": "右侧敏感度（%）",
    "left_positive_gain": "左侧正向增益",
    "left_negative_gain": "左侧负向增益",
    "right_positive_gain": "右侧正向增益",
    "right_negative_gain": "右侧负向增益",
}


async def run_style_score_test(  # noqa: PLR0912, PLR0915
    db: AsyncSession, *, style_id: int, form_data: dict[str, Any]
) -> dict[str, Any]:
    """
    Execute per-dimension mapping + offset + candidate selection for style test.

    Returns a structure compatible with admin template ai_style_test.html.
    """
    current_relationship_id: int | None = None
    try:
        dims_q = text(
            """
            SELECT d.id AS id, d.name AS name, d.display_name AS display_name,
            asd.initial_position AS initial_position
            FROM ai_style_dimensions AS asd
            JOIN ai_dimensions AS d ON d.id = asd.dimension_id
            WHERE asd.style_id = :style_id
            ORDER BY d.name
            """
        )
        result = await db.execute(dims_q, {"style_id": int(style_id)})
        dims = result.fetchall()
        if not dims:
            _style_test_fail("该风格未配置维度")

        raw_current_rel = form_data.get("current_relationship")
        if raw_current_rel:
            try:
                current_relationship_id = int(raw_current_rel)
            except (TypeError, ValueError):
                _style_test_fail("current_relationship 参数无效")

        dimension_results: list[dict[str, Any]] = []
        all_candidates: list[RelationshipCandidate] = []

        for dim in dims:
            dim_name = dim.name
            dim_algo_key = f"algorithm_{dim_name}"
            try:
                algorithm = int(form_data.get(dim_algo_key, "1"))
            except (TypeError, ValueError):
                _style_test_fail(f"{dim.display_name} 的算法参数无效")

            params: dict[str, Any] = {}
            if algorithm == PositionMappingAlgorithm.V1.value:
                raw_params: dict[str, Any] = {}
                missing_fields: list[str] = []
                for spec in V1_PARAM_SPECS:
                    field_key = f"{spec['name']}_{dim_name}"
                    raw_value = form_data.get(field_key)
                    if raw_value is None or str(raw_value).strip() == "":
                        label = V1_PARAM_LABELS_ZH.get(spec["name"], str(spec["label"]))
                        missing_fields.append(label)
                        continue
                    raw_params[spec["name"]] = raw_value

                if missing_fields:
                    joined = ", ".join(missing_fields)
                    _style_test_fail(f"{dim.display_name} 缺少 V1 参数（{joined}）")

                try:
                    params = parse_algorithm_params(PositionMappingAlgorithm.V1, raw_params)
                except ValueError as exc:
                    _style_test_fail(f"{dim.display_name} 的 V1 参数无效：{exc}")

            try:
                s_raw = form_data.get(f"score_{dim_name}")
                smin_raw = form_data.get(f"score_min_{dim_name}")
                smax_raw = form_data.get(f"score_max_{dim_name}")
                if s_raw is None or smin_raw is None or smax_raw is None:
                    raise ValueError("missing_scores")
                score = float(str(s_raw))
                score_min = float(str(smin_raw))
                score_max = float(str(smax_raw))
            except (TypeError, ValueError):
                _style_test_fail(f"{dim.display_name} 缺少分数字段")

            try:
                mapped = map_to_permille(score, score_min, score_max)
            except Exception as exc:
                logger.error(
                    "admin_score_mapping_failed",
                    dimension=dim_name,
                    error=str(exc),
                )
                _style_test_fail(f"{dim.display_name} 的分数映射失败")

            final_position = map_score_to_position(
                algorithm=algorithm,
                score=float(mapped),
                initial_position=dim.initial_position,
                params=params,
            )

            mapped_i = max(0, min(1000, int(float(mapped) + 0.5)))
            final_i = max(0, min(1000, int(float(final_position) + 0.5)))

            candidates = await collect_candidates(
                db,
                style_id=int(style_id),
                dimension_id=int(dim.id),
                position=final_i,
            )

            if current_relationship_id is not None and candidates:
                current_in_candidates = any(
                    int(c.get("relationship_id")) == int(current_relationship_id)
                    for c in candidates
                )
                if current_in_candidates:
                    candidates = [
                        c
                        for c in candidates
                        if int(c.get("relationship_id")) == int(current_relationship_id)
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

        rel_to_dims: dict[int, set[str]] = {}
        for dr in dimension_results:
            dims_disp = dr.get("dimension_display_name")
            for c in dr.get("candidates") or []:
                try:
                    rrid = int(c.get("relationship_id"))
                except (TypeError, ValueError) as exc:
                    logger.warning(
                        "style_test_invalid_relationship_id",
                        candidate=c,
                        error=str(exc),
                    )
                    continue
                if rrid not in rel_to_dims:
                    rel_to_dims[rrid] = set()
                if dims_disp:
                    rel_to_dims[rrid].add(str(dims_disp))

        unique: dict[int, dict[str, Any]] = {}
        for c in all_candidates:
            rid = int(c["relationship_id"])
            pr = int(c.get("priority", 0))
            if rid not in unique:
                unique[rid] = {
                    "relationship_id": rid,
                    "relationship_display_name": c.get("relationship_display_name"),
                    "prompt_fragment": c.get("prompt_fragment"),
                    "count": 0,
                    "best_priority": pr,
                    "dimension_display_names": sorted(rel_to_dims.get(rid, set())),
                }
            unique[rid]["count"] += 1
            unique[rid]["best_priority"] = min(pr, unique[rid]["best_priority"])

        all_unique_candidates = list(unique.values())

        selection = select_final_relationship(all_candidates, higher_is_better=False)
        selected_relationship = selection.get("relationship")
        reason = selection.get("reason")

        return {
            "success": True,
            "dimension_results": dimension_results,
            "all_unique_candidates": all_unique_candidates,
            "selected_relationship": selected_relationship,
            "selection_reason": reason,
            "current_relationship_id": current_relationship_id,
        }
    except StyleTestError as exc:
        return {"success": False, "message": str(exc)}

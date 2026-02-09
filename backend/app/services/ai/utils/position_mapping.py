"""
Position mapping algorithm implementations.

This module provides pure functions for mapping LLM output scores to final position values
with optional offset adjustments using various algorithms.
All algorithms are stateless and maintain initial position as origin.
"""

import math
from typing import Any, cast

from app.enums.common import PositionMappingAlgorithm
from app.type_defs import AlgorithmParameterSpec, JSONDict, JSONValue, V1Params
from app.utils.logging import get_logger

logger = get_logger(__name__)

EPSILON = 1e-10  # Numerical stability threshold for floating-point comparisons
SCORE_MIN = 0.0
SCORE_MAX = 1000.0
SENSITIVITY_MIN = -100.0
SENSITIVITY_MAX = 100.0

Numeric = int | float


ALGORITHM_PARAM_SPECS: dict[PositionMappingAlgorithm, list[AlgorithmParameterSpec]] = {
    PositionMappingAlgorithm.V1: [
        {
            "name": "left_sensitivity",
            "label": "Left Sensitivity (%)",
            "description": (
                "Sensitivity factor for positions below the initial position (-100 to 100)."
            ),
            "input_type": "integer",
            "min": -100,
            "max": 100,
            "step": 1,
            "required": True,
        },
        {
            "name": "right_sensitivity",
            "label": "Right Sensitivity (%)",
            "description": (
                "Sensitivity factor for positions above the initial position (-100 to 100)."
            ),
            "input_type": "integer",
            "min": -100,
            "max": 100,
            "step": 1,
            "required": True,
        },
        {
            "name": "left_positive_gain",
            "label": "Left Positive Gain",
            "description": "Logarithmic gain applied when the left segment sensitivity is ≥ 0.",
            "input_type": "integer",
            "min": 1,
            "max": 10000,
            "step": 1,
            "required": True,
        },
        {
            "name": "left_negative_gain",
            "label": "Left Negative Gain",
            "description": "Logarithmic gain applied when the left segment sensitivity is < 0.",
            "input_type": "integer",
            "min": 1,
            "max": 10000,
            "step": 1,
            "required": True,
        },
        {
            "name": "right_positive_gain",
            "label": "Right Positive Gain",
            "description": "Logarithmic gain applied when the right segment sensitivity is ≥ 0.",
            "input_type": "integer",
            "min": 1,
            "max": 10000,
            "step": 1,
            "required": True,
        },
        {
            "name": "right_negative_gain",
            "label": "Right Negative Gain",
            "description": "Logarithmic gain applied when the right segment sensitivity is < 0.",
            "input_type": "integer",
            "min": 1,
            "max": 10000,
            "step": 1,
            "required": True,
        },
    ]
}


def _normalize_algorithm(algorithm: int | PositionMappingAlgorithm) -> PositionMappingAlgorithm:
    """Coerce raw algorithm identifiers into enum values."""

    if isinstance(algorithm, PositionMappingAlgorithm):
        return algorithm
    return PositionMappingAlgorithm(int(algorithm))


def _clone_specs(specs: list[AlgorithmParameterSpec]) -> list[AlgorithmParameterSpec]:
    """Return a shallow copy of specs to prevent accidental mutation."""

    return [cast(AlgorithmParameterSpec, dict(spec)) for spec in specs]


def _coerce_numeric_param(value: JSONValue, spec: AlgorithmParameterSpec) -> Numeric:
    """Convert a raw value into the numeric type required by the spec."""

    raw_value: JSONValue = value
    if raw_value is None:
        raise ValueError(f"{spec['label']} is required")

    if isinstance(raw_value, str):
        raw_value = raw_value.strip()
        if raw_value == "":
            raise ValueError(f"{spec['label']} is required")

    if not isinstance(raw_value, str | int | float):
        raise TypeError(f"{spec['label']} must be a number")

    try:
        number = float(raw_value)
    except (TypeError, ValueError):
        raise ValueError(f"{spec['label']} must be a number")

    if spec["input_type"] == "integer":
        if not number.is_integer():
            raise ValueError(f"{spec['label']} must be an integer")
        coerced: Numeric = int(number)
    else:
        coerced = number

    if spec["min"] is not None and coerced < spec["min"]:
        raise ValueError(f"{spec['label']} must be ≥ {spec['min']}")
    if spec["max"] is not None and coerced > spec["max"]:
        raise ValueError(f"{spec['label']} must be ≤ {spec['max']}")

    return coerced


def get_algorithm_param_specs(
    algorithm: int | PositionMappingAlgorithm | None = None,
) -> dict[int, list[AlgorithmParameterSpec]]:
    """
    Return parameter specifications for algorithms.

    Args:
        algorithm:
            Optional algorithm identifier. When provided, only that algorithm's
            specs are returned.

    Returns:
        Mapping of algorithm enum value to its parameter specs.
    """

    if algorithm is None:
        return {alg.value: _clone_specs(specs) for alg, specs in ALGORITHM_PARAM_SPECS.items()}

    algorithm_enum = _normalize_algorithm(algorithm)
    return {algorithm_enum.value: _clone_specs(ALGORITHM_PARAM_SPECS.get(algorithm_enum, []))}


def parse_algorithm_params(
    algorithm: int | PositionMappingAlgorithm,
    params: JSONDict,
) -> dict[str, Numeric]:
    """
    Normalize and validate algorithm parameters according to the registered spec.

    Args:
        algorithm: Algorithm identifier
        params: Raw parameter dictionary (e.g., from API payload)

    Returns:
        Dict containing normalized numeric parameters

    Raises:
        ValueError: If required parameters are missing or invalid
    """

    algorithm_enum = _normalize_algorithm(algorithm)
    specs = ALGORITHM_PARAM_SPECS.get(algorithm_enum, [])
    if not specs:
        return {}

    parsed: dict[str, Numeric] = {}
    missing_labels: list[str] = []

    for spec in specs:
        raw_value = params.get(spec["name"])
        if raw_value is None or (isinstance(raw_value, str) and raw_value.strip() == ""):
            if spec["required"]:
                missing_labels.append(spec["label"])
            continue

        parsed[spec["name"]] = _coerce_numeric_param(raw_value, spec)

    if missing_labels:
        raise ValueError(f"Missing parameters: {', '.join(missing_labels)}")

    return parsed


def map_score_to_position(
    algorithm: int,
    score: float,
    initial_position: float,
    params: JSONDict | None = None,
) -> float:
    """
    Map LLM output score to final position value using specified algorithm.

    This is the main entry point for position mapping.

    Args:
        algorithm: Algorithm type from PositionMappingAlgorithm enum
        score: LLM response score value (0-1000)
        initial_position: Initial position from ai_style_dimensions (0-1000)
        params: Algorithm-specific parameters (all required for V1)

    Returns:
        Final position value (0-1000)

    Raises:
        ValueError: If algorithm is unknown or parameters are invalid
    """

    if params is None:
        params = {}

    if not (SCORE_MIN <= score <= SCORE_MAX):
        raise ValueError(f"Score must be between {SCORE_MIN} and {SCORE_MAX}, got: {score}")
    if not (SCORE_MIN <= initial_position <= SCORE_MAX):
        raise ValueError(
            f"Initial position must be between {SCORE_MIN} and {SCORE_MAX}, got: {initial_position}"
        )

    try:
        algorithm_enum = _normalize_algorithm(algorithm)
    except ValueError:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    try:
        if algorithm_enum == PositionMappingAlgorithm.NONE:
            return calculate_none_mapping(score, initial_position)
        if algorithm_enum == PositionMappingAlgorithm.V1:
            validated = parse_algorithm_params(algorithm_enum, params)
            return calculate_v1_mapping(score, initial_position, cast(V1Params, validated))
        raise ValueError(f"Algorithm not implemented: {algorithm}")
    except Exception as e:
        logger.error(
            "position_mapping_calculation_failed",
            algorithm=algorithm,
            score=score,
            initial_position=initial_position,
            params=params,
            error=str(e),
            exc_info=True,
        )
        raise


def calculate_none_mapping(
    score: float, _initial_position: float, _params: JSONDict | None = None
) -> float:
    """
    Direct mapping without any offset - returns LLM score directly.

    Args:
        score: LLM response score (0-1000)
        _initial_position: Placeholder for consistency with other algorithms
        _params: Placeholder for consistency with other algorithms

    Returns:
        The same score value, clamped to valid range
    """

    return max(SCORE_MIN, min(SCORE_MAX, score))


def calculate_v1_mapping(score: float, initial_position: float, params: V1Params) -> float:
    """
    V1 algorithm: Nonlinear position mapping with sensitivity-controlled offset.

    Maps score to position distance [0, 1000] with initial_position as origin.
    Left and right segments use mirrored calculation with independent sensitivity
    control. Uses logarithmic function for nonlinear acceleration near threshold.

    Args:
        score: LLM output score (0-1000)
        initial_position: Initial position from dimension config (0-1000)
        params: Algorithm parameters
            - left_sensitivity/right_sensitivity: [-100, 100], sensitivity controls
            - left_positive_gain/left_negative_gain/right_positive_gain/right_negative_gain:
                [1, 100], logarithmic gains

    Returns:
        Final mapped position (0-1000)
    """

    left_sensitivity = float(params["left_sensitivity"])
    right_sensitivity = float(params["right_sensitivity"])
    left_positive_gain = float(params["left_positive_gain"])
    left_negative_gain = float(params["left_negative_gain"])
    right_positive_gain = float(params["right_positive_gain"])
    right_negative_gain = float(params["right_negative_gain"])

    # Determine distance from initial position
    _initial_position = initial_position
    distance = abs(score - _initial_position)

    if distance == 0:
        return _initial_position

    if score < _initial_position:
        # Left segment calculations
        relative_position = distance / max(_initial_position, EPSILON)

        if left_sensitivity >= SENSITIVITY_MAX:
            position = 0.0
        elif left_sensitivity <= SENSITIVITY_MIN:
            position = _initial_position
        else:
            if left_sensitivity >= 0:
                offset_ratio = (
                    -left_positive_gain
                    * math.log(
                        max(
                            (1 - relative_position / (1.12 - left_sensitivity / 100) / 2.5), EPSILON
                        )
                    )
                    / 100.0
                )
            else:
                offset_ratio = (
                    -left_negative_gain
                    * math.log(
                        max((1 - relative_position / (1.12 - left_sensitivity / 100)), EPSILON)
                    )
                    / 100.0
                )
                offset_ratio = max(0.0, min(1.0, offset_ratio))

            position = _initial_position * offset_ratio
    else:
        # Right segment calculations
        max_range = SCORE_MAX - _initial_position
        relative_position = distance / max(max_range, EPSILON)

        if right_sensitivity >= SENSITIVITY_MAX:
            position = 1000.0
        elif right_sensitivity <= SENSITIVITY_MIN:
            position = _initial_position
        else:
            if right_sensitivity >= 0:
                offset_ratio = (
                    -right_positive_gain
                    * math.log(
                        max(
                            (1 - relative_position / (1.12 - right_sensitivity / 100 / 2.5)),
                            EPSILON,
                        )
                    )
                    / 100.0
                )
            else:
                offset_ratio = (
                    -right_negative_gain
                    * math.log(
                        max((1 - relative_position / (1.12 - right_sensitivity / 100)), EPSILON)
                    )
                    / 100.0
                )
                offset_ratio = max(0.0, min(1.0, offset_ratio))

            position = _initial_position + max_range * offset_ratio

    return max(SCORE_MIN, min(SCORE_MAX, position))


def get_algorithm_info(algorithm: int) -> dict[str, Any]:
    """
    Get information about a specific algorithm.

    Args:
        algorithm: Algorithm type from PositionMappingAlgorithm enum

    Returns:
        Dictionary containing algorithm information
    """

    try:
        algorithm_enum = _normalize_algorithm(algorithm)
    except ValueError:
        return {
            "name": "Unknown",
            "descr_initial_positiontion": "Unknown algorithm",
            "parameters": [],
            "formula": "N/A",
        }

    if algorithm_enum == PositionMappingAlgorithm.NONE:
        return {
            "name": "None (direct)",
            "version": "1.0",
            "descr_initial_positiontion": ("Direct score to position mapping without offset"),
            "parameters": [],
            "formula": "position = score",
        }
    # V1 algorithm
    specs = ALGORITHM_PARAM_SPECS.get(algorithm_enum, [])
    return {
        "name": "V1",
        "version": "6.0",
        "descr_initial_positiontion": (
            "Nonlinear position mapping with sensitivity-controlled logarithmic offset."
        ),
        "parameters": [
            {
                "name": spec["name"],
                "type": spec["input_type"],
                "label": spec["label"],
                "required": spec["required"],
                "range": (
                    [spec["min"], spec["max"]]
                    if spec["min"] is not None or spec["max"] is not None
                    else None
                ),
                "descr_initial_positiontion": spec["description"],
            }
            for spec in specs
        ],
        "formula": (
            "offset_ratio = -gain * ln(1 - ratio) / 100; position = initial ± "
            "distance * offset_ratio, using independent left/right "
            "sensitivities and gains."
        ),
    }


def validate_algorithm_params(algorithm: int, params: JSONDict) -> bool:
    """
    Validate parameters for a specific algorithm.

    Args:
        algorithm: Algorithm type from PositionMappingAlgorithm enum
        params: Parameters to validate

    Returns:
        True if parameters are valid, False otherwise
    """

    try:
        parse_algorithm_params(algorithm, params)
        return True
    except Exception:
        return False

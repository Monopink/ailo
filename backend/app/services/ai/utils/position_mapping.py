"""
Position mapping algorithm implementations.

This module provides pure functions for mapping LLM output scores to final position values
with optional offset adjustments using various algorithms.
All algorithms are stateless and maintain initial position as origin.
"""

import math
from typing import Dict, Any, Optional
from enums.common import PositionMappingAlgorithm
from utils.logging import get_logger

logger = get_logger(__name__)


# Algorithm constants
# Left segment coefficients
V1_K_LEFT_POSITIVE = 45  # For left segment when sensitivity >= 0
V1_K_LEFT_NEGATIVE = 39  # For left segment when sensitivity < 0

# Right segment coefficients
V1_K_RIGHT_POSITIVE = 45  # For right segment when sensitivity >= 0
V1_K_RIGHT_NEGATIVE = 39  # For right segment when sensitivity < 0

EPSILON = 1e-10  # Numerical stability threshold for floating-point comparisons


# Default parameters for different algorithms
DEFAULT_ALGORITHM_PARAMS = {
    PositionMappingAlgorithm.NONE: {},
    PositionMappingAlgorithm.V1: {
        "left_sensitivity": 0,  # -100 to 100, left segment sensitivity control
        "right_sensitivity": 0,  # -100 to 100, right segment sensitivity control
    },
}


def map_score_to_position(
    algorithm: int, score: float, initial_position: float, params: Optional[Dict[str, Any]] = None
) -> float:
    """
    Map LLM output score to final position value using specified algorithm.

    This is the main entry point for position mapping.

    Args:
        algorithm: Algorithm type from PositionMappingAlgorithm enum
        score: LLM response score value (0-1000)
        initial_position: Initial position from ai_style_dimensions (0-1000)
        params: Algorithm-specific parameters

    Returns:
        Final position value (0-1000)

    Raises:
        ValueError: If algorithm is unknown or parameters are invalid
    """
    if params is None:
        params = {}

    # Validate inputs
    if not (0 <= score <= 1000):
        raise ValueError(f"Score must be between 0 and 1000, got: {score}")
    if not (0 <= initial_position <= 1000):
        raise ValueError(f"Initial position must be between 0 and 1000, got: {initial_position}")

    try:
        algorithm_enum = PositionMappingAlgorithm(algorithm)
    except ValueError:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    # Merge with default parameters
    default_params = DEFAULT_ALGORITHM_PARAMS.get(algorithm_enum, {})
    merged_params = {**default_params, **params}

    try:
        if algorithm_enum == PositionMappingAlgorithm.NONE:
            return calculate_none_mapping(score, initial_position, merged_params)
        elif algorithm_enum == PositionMappingAlgorithm.V1:
            return calculate_v1_mapping(score, initial_position, merged_params)
        else:
            raise ValueError(f"Algorithm not implemented: {algorithm}")

    except Exception as e:
        logger.error(
            "position_mapping_calculation_failed",
            algorithm=algorithm,
            score=score,
            initial_position=initial_position,
            params=merged_params,
            error=str(e),
            exc_info=True,
        )
        raise


def calculate_none_mapping(score: float, initial_position: float, params: Dict[str, Any]) -> float:
    """
    Direct mapping without any offset - returns LLM score directly.

    Args:
        score: LLM response score (0-1000)
        initial_position: Not used for this algorithm
        params: Not used for this algorithm

    Returns:
        The same score value, clamped to valid range
    """
    return max(0.0, min(1000.0, score))


def calculate_v1_mapping(score: float, initial_position: float, params: Dict[str, Any]) -> float:
    """
    V1 algorithm: Nonlinear position mapping with sensitivity-controlled offset.

    Maps score to position distance [0, 1000] with initial_position as origin.
    Left and right segments use mirrored calculation with independent sensitivity control.
    Uses logarithmic function for nonlinear acceleration near threshold.

    Args:
        score: LLM output score (0-1000)
        initial_position: Initial position from dimension config (0-1000)
        params: Algorithm parameters
            - left_sensitivity: -100 to 100, left segment sensitivity control
            - right_sensitivity: -100 to 100, right segment sensitivity control

    Returns:
        Final position value (0-1000)

    Raises:
        ValueError: If parameters are invalid
    """
    # Extract and validate parameters
    left_sensitivity = params.get("left_sensitivity", 0)
    right_sensitivity = params.get("right_sensitivity", 0)

    if not (-100 <= left_sensitivity <= 100):
        raise ValueError(f"left_sensitivity must be in [-100, 100], got: {left_sensitivity}")
    if not (-100 <= right_sensitivity <= 100):
        raise ValueError(f"right_sensitivity must be in [-100, 100], got: {right_sensitivity}")

    # Step 0: Clamp inputs to valid range (defensive programming)
    _score = max(0.0, min(1000.0, score))
    _initial_position = max(0.0, min(1000.0, initial_position))

    # Handle edge cases where _initial_position is at boundaries
    # When _initial_position=0, only right side exists; when _initial_position=1000, only left side exists
    # In these cases, no meaningful offset can be calculated, return original score
    if _initial_position <= EPSILON:
        return _score
    if _initial_position >= 1000.0 - EPSILON:
        return _score

    # Handle special case: score equals _initial_position (at origin point)
    # No offset needed, return _initial_position directly
    if abs(_score - _initial_position) < EPSILON:
        return _initial_position

    # Step 1: Determine segment and calculate offset
    if _score < _initial_position:
        # Left segment: [0, _initial_position]
        distance = _initial_position

        # Handle boundary cases for left_sensitivity
        if left_sensitivity >= 100:
            # Maximum sensitivity: always full offset
            offset_ratio = 1.0
        elif left_sensitivity <= -100:
            # Minimum sensitivity: no offset
            offset_ratio = 0.0
        else:
            # Calculate normalized distance from origin
            relative_position = (_initial_position - _score) / _initial_position

            # Different formulas based on sensitivity sign
            if left_sensitivity >= 0:
                # Positive sensitivity: standard logarithmic formula
                # offset_ratio = -V1_K_LEFT_POSITIVE * LN(1 - ratio) / 100
                offset_ratio = (
                    -V1_K_LEFT_POSITIVE
                    * math.log(
                        max((1 - relative_position / (1.12 - left_sensitivity / 100) / 2.5), EPSILON)
                    )
                    / 100.0
                )
            else:
                # Negative sensitivity: alternative formula
                # offset_ratio = -V1_K_LEFT_NEGATIVE * LN(1 - ratio / 2) / 100
                offset_ratio = (
                    -V1_K_LEFT_NEGATIVE
                    * math.log(max((1 - relative_position / (1.12 - left_sensitivity / 100)), EPSILON))
                    / 100.0
                )

                # Clamp offset_ratio to [0, 1] to prevent overflow
                offset_ratio = max(0.0, min(1.0, offset_ratio))

        # Map back to original distance
        position = _initial_position - distance * offset_ratio

    else:
        # Right segment: [_initial_position, 1000]
        distance = 1000.0 - _initial_position

        # Handle boundary cases for right_sensitivity
        if right_sensitivity >= 100:
            # Maximum sensitivity: always full offset
            offset_ratio = 1.0
        elif right_sensitivity <= -100:
            # Minimum sensitivity: no offset
            offset_ratio = 0.0
        else:
            # Calculate normalized distance from origin
            relative_position = (_score - _initial_position) / (1000.0 - _initial_position)

            # Different formulas based on sensitivity sign
            if right_sensitivity >= 0:
                # Positive sensitivity: standard logarithmic formula
                # offset_ratio = -V1_K_RIGHT_POSITIVE * LN(1 - ratio) / 100
                offset_ratio = (
                    -V1_K_RIGHT_POSITIVE
                    * math.log(
                        max((1 - relative_position / (1.12 - right_sensitivity / 100 / 2.5)), EPSILON)
                    )
                    / 100.0
                )
            else:
                # Negative sensitivity: alternative formula
                # offset_ratio = -V1_K_RIGHT_NEGATIVE * LN(1 - ratio / 2) / 100
                offset_ratio = (
                    -V1_K_RIGHT_NEGATIVE
                    * math.log(max((1 - relative_position / (1.12 - right_sensitivity / 100)), EPSILON))
                    / 100.0
                )

                # Clamp offset_ratio to [0, 1] to prevent overflow
                offset_ratio = max(0.0, min(1.0, offset_ratio))

        # Map back to original distance
        position = _initial_position + distance * offset_ratio

    # Final safety clamp to ensure result is within valid range
    return max(0.0, min(1000.0, position))


def get_algorithm_info(algorithm: int) -> Dict[str, Any]:
    """
    Get information about a specific algorithm.

    Args:
        algorithm: Algorithm type from PositionMappingAlgorithm enum

    Returns:
        Dictionary containing algorithm information
    """
    try:
        algorithm_enum = PositionMappingAlgorithm(algorithm)
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
            "descr_initial_positiontion": "Direct score to position mapping without offset",
            "parameters": [],
            "formula": "position = score",
        }
    elif algorithm_enum == PositionMappingAlgorithm.V1:
        return {
            "name": "V1",
            "version": "5.0",
            "descr_initial_positiontion": "Nonlinear position mapping with sensitivity-controlled logarithmic offset. Uses fixed distance mapping with mirrored left/right calculation, monotonically increasing, nonlinear acceleration near threshold.",
            "parameters": [
                {
                    "name": "left_sensitivity",
                    "type": "integer",
                    "default": 0,
                    "range": [-100, 100],
                    "descr_initial_positiontion": "Left segment sensitivity control: 100 (most sensitive) to -100 (least sensitive)",
                },
                {
                    "name": "right_sensitivity",
                    "type": "integer",
                    "default": 0,
                    "range": [-100, 100],
                    "descr_initial_positiontion": "Right segment sensitivity control: 100 (most sensitive) to -100 (least sensitive)",
                },
            ],
            "formula": "if sensitivity=100: offset_ratio=1; elif sensitivity=-100: offset_ratio=0; else: threshold=1-sensitivity/100, ratio=relative_position/threshold, offset_ratio=-K*ln(1-ratio)/100; position=_initial_position±distance*offset_ratio",
        }
    else:
        return {
            "name": "Unknown",
            "version": "0.0",
            "descr_initial_positiontion": "Unknown algorithm",
            "parameters": [],
            "formula": "N/A",
        }


def validate_algorithm_params(algorithm: int, params: Dict[str, Any]) -> bool:
    """
    Validate parameters for a specific algorithm.

    Args:
        algorithm: Algorithm type from PositionMappingAlgorithm enum
        params: Parameters to validate

    Returns:
        True if parameters are valid, False otherwise
    """
    try:
        algorithm_enum = PositionMappingAlgorithm(algorithm)
    except ValueError:
        return False

    if algorithm_enum == PositionMappingAlgorithm.NONE:
        # No parameters needed
        return True
    elif algorithm_enum == PositionMappingAlgorithm.V1:
        # Validate left_sensitivity and right_sensitivity parameters
        required_params = ["left_sensitivity", "right_sensitivity"]
        for param in required_params:
            if param not in params:
                return False

        # Validate left_sensitivity range
        if not isinstance(params["left_sensitivity"], (int, float)) or not (
            -100 <= params["left_sensitivity"] <= 100
        ):
            return False

        # Validate right_sensitivity range
        if not isinstance(params["right_sensitivity"], (int, float)) or not (
            -100 <= params["right_sensitivity"] <= 100
        ):
            return False

        return True
    else:
        return False

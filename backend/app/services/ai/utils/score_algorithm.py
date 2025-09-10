"""
Score offset algorithm implementations.

This module provides pure functions for calculating score offsets
based on relationship scores using various algorithms.
All algorithms are stateless and maintain initial position as origin.
"""

import math
from typing import Dict, Any, Optional
from enums import ScoreOffsetAlgorithm
from utils.logging import get_logger

logger = get_logger(__name__)


# Default parameters for different algorithms
DEFAULT_ALGORITHM_PARAMS = {
    ScoreOffsetAlgorithm.NONE: {},
    ScoreOffsetAlgorithm.V1: {
        "strength": 0.5,  # Non-linear strength factor (0.0-1.0)
    },
}


def apply_score_algorithm(
    algorithm: int, score: float, initial_position: float, params: Optional[Dict[str, Any]] = None
) -> float:
    """
    Apply score offset algorithm to calculate new position.

    This is the main entry point for score calculation.

    Args:
        algorithm: Algorithm type from ScoreOffsetAlgorithm enum
        score: LLM response score value (0-1000)
        initial_position: Initial position from ai_relationship_dimensions (0-1000)
        params: Algorithm-specific parameters

    Returns:
        New score position (0-1000)

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
        algorithm_enum = ScoreOffsetAlgorithm(algorithm)
    except ValueError:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    # Merge with default parameters
    default_params = DEFAULT_ALGORITHM_PARAMS.get(algorithm_enum, {})
    merged_params = {**default_params, **params}

    try:
        if algorithm_enum == ScoreOffsetAlgorithm.NONE:
            return calculate_none_offset(score, initial_position, merged_params)
        elif algorithm_enum == ScoreOffsetAlgorithm.V1:
            return calculate_v1_offset(score, initial_position, merged_params)
        else:
            raise ValueError(f"Algorithm not implemented: {algorithm}")

    except Exception as e:
        logger.error(
            "score_algorithm_calculation_failed",
            algorithm=algorithm,
            score=score,
            initial_position=initial_position,
            params=merged_params,
            error=str(e),
            exc_info=True,
        )
        raise


def calculate_none_offset(score: float, initial_position: float, params: Dict[str, Any]) -> float:
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


def calculate_v1_offset(score: float, initial_position: float, params: Dict[str, Any]) -> float:
    """
    V1 algorithm using simplified non-linear offset based on initial position.

    This algorithm:
    - Uses initial_position as the baseline
    - Applies non-linear offset based on LLM score
    - Provides configurable curve strength

    Args:
        score: LLM response score (0-1000)
        initial_position: Initial position from dimension config (0-1000)
        params: Algorithm parameters containing strength

    Returns:
        New score position (0-1000)

    Raises:
        ValueError: If parameters are invalid
    """
    strength = params.get("strength", 0.5)

    # Validate parameters
    if not (0.0 <= strength <= 1.0):
        raise ValueError("strength must be between 0.0 and 1.0")
    if score < 0:
        raise ValueError("score cannot be negative")

    try:
        # Calculate direction and distance
        direction = score - initial_position

        if direction == 0:
            return initial_position

        # Normalize direction to [-1, 1] range
        max_distance = 500.0  # Maximum possible distance
        normalized_direction = direction / max_distance

        # Apply non-linear curve (exponential function)
        # strength > 0: enhance offset effect
        # strength = 0: linear offset
        curve_factor = 1 + strength
        curved_offset = (
            math.copysign(abs(normalized_direction) ** curve_factor, normalized_direction) * max_distance
        )

        # Calculate final position
        final_position = initial_position + curved_offset

        # Ensure result is within valid range
        final_position = max(0.0, min(1000.0, final_position))

        logger.debug(
            "v1_algorithm_applied",
            score=score,
            initial_position=initial_position,
            direction=direction,
            normalized_direction=normalized_direction,
            curve_factor=curve_factor,
            curved_offset=curved_offset,
            final_position=final_position,
            strength=strength,
        )

        return final_position

    except (ValueError, OverflowError) as e:
        logger.error(
            "v1_algorithm_calculation_error",
            score=score,
            initial_position=initial_position,
            strength=strength,
            error=str(e),
        )
        raise ValueError(f"V1 algorithm calculation failed: {str(e)}")


def get_algorithm_info(algorithm: int) -> Dict[str, Any]:
    """
    Get information about a specific algorithm.

    Args:
        algorithm: Algorithm type from ScoreOffsetAlgorithm enum

    Returns:
        Dictionary containing algorithm information
    """
    try:
        algorithm_enum = ScoreOffsetAlgorithm(algorithm)
    except ValueError:
        return {
            "name": "Unknown",
            "description": "Unknown algorithm",
            "parameters": [],
            "formula": "N/A",
        }

    if algorithm_enum == ScoreOffsetAlgorithm.NONE:
        return {
            "name": "Direct Mapping",
            "version": "1.0",
            "description": "No offset applied, direct score mapping",
            "parameters": [],
            "formula": "output = input",
        }
    elif algorithm_enum == ScoreOffsetAlgorithm.V1:
        return {
            "name": "V1 Non-linear Offset",
            "version": "1.0",
            "description": "Simplified non-linear offset based on initial position",
            "parameters": [
                {
                    "name": "strength",
                    "type": "float",
                    "default": 0.5,
                    "description": "Non-linear strength factor (0.0-1.0)",
                },
            ],
            "formula": "final_position = initial_position + curved_offset",
        }
    else:
        return {
            "name": "Unknown",
            "version": "0.0",
            "description": "Unknown algorithm",
            "parameters": [],
            "formula": "N/A",
        }


def validate_algorithm_params(algorithm: int, params: Dict[str, Any]) -> bool:
    """
    Validate parameters for a specific algorithm.

    Args:
        algorithm: Algorithm type from ScoreOffsetAlgorithm enum
        params: Parameters to validate

    Returns:
        True if parameters are valid, False otherwise
    """
    try:
        algorithm_enum = ScoreOffsetAlgorithm(algorithm)
    except ValueError:
        return False

    if algorithm_enum == ScoreOffsetAlgorithm.NONE:
        # No parameters needed
        return True
    elif algorithm_enum == ScoreOffsetAlgorithm.V1:
        required_params = ["strength"]
        for param in required_params:
            if param not in params:
                return False
            if not isinstance(params[param], (int, float)):
                return False
            # Validate strength is between 0.0 and 1.0
            if param == "strength" and not (0.0 <= params[param] <= 1.0):
                return False
        return True
    else:
        return False

"""
Position mapping algorithm implementations.

This module provides pure functions for mapping LLM output scores to final position values
with optional offset adjustments using various algorithms.
All algorithms are stateless and maintain initial position as origin.
"""

from typing import Dict, Any, Optional
from enums.common import PositionMappingAlgorithm
from utils.logging import get_logger

logger = get_logger(__name__)


# Default parameters for different algorithms
DEFAULT_ALGORITHM_PARAMS = {
    PositionMappingAlgorithm.NONE: {},
    PositionMappingAlgorithm.V1: {
        "left_bias": 0,  # -100 to 100, left side offset control
        "right_bias": 0,  # -100 to 100, right side offset control
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
    V1 algorithm with independent bidirectional offset control.

    This algorithm supports:
    - Independent control for left and right side offsets
    - Bidirectional offset (both towards endpoints and towards origin)
    - Similar to Photoshop curve adjustment
    - Algorithm itself guarantees staying within 0-1000 range
    - Mapping magnitude is proportional to segment length

    Args:
        score: LLM output score (0-1000)
        initial_position: Initial position from dimension config (0-1000)
        params: Algorithm parameters
            - left_bias: -100 to 100, left side offset control
            - right_bias: -100 to 100, right side offset control

    Returns:
        Final position value (0-1000)

    Raises:
        ValueError: If parameters are invalid
    """
    left_bias = params.get("left_bias", 0)  # -100 to 100
    right_bias = params.get("right_bias", 0)  # -100 to 100

    # Validate parameters
    if not (-100 <= left_bias <= 100):
        raise ValueError("left_bias must be between -100 and 100")
    if not (-100 <= right_bias <= 100):
        raise ValueError("right_bias must be between -100 and 100")
    if score < 0 or initial_position < 0:
        raise ValueError("score and initial_position cannot be negative")

    try:
        # initial_position always maps to itself
        if score == initial_position:
            return initial_position

        if score < initial_position:
            # Left side interval [0, initial_position]
            if initial_position == 0:
                return score

            # Calculate relative position [0, 1]
            relative_pos = score / initial_position

            # Apply left side offset curve
            if left_bias == 0:
                # Linear, no adjustment
                adjusted_pos = relative_pos
            elif left_bias < 0:
                # Towards origin: compress towards initial_position
                compression_factor = abs(left_bias) / 100.0
                adjusted_pos = relative_pos * (1.0 - compression_factor)
            else:
                # Towards endpoints: stretch towards 0
                stretch_factor = left_bias / 100.0
                adjusted_pos = max(0.0, relative_pos * (1.0 - stretch_factor))

            return adjusted_pos * initial_position

        else:
            # Right side interval [initial_position, 1000]
            if initial_position == 1000:
                return score

            right_range = 1000.0 - initial_position
            relative_pos = (score - initial_position) / right_range

            # Apply right side offset curve
            if right_bias == 0:
                # Linear, no adjustment
                adjusted_pos = relative_pos
            elif right_bias < 0:
                # Towards origin: compress towards initial_position
                compression_factor = abs(right_bias) / 100.0
                adjusted_pos = relative_pos * (1.0 - compression_factor)
            else:
                # Towards endpoints: stretch towards 1000
                stretch_factor = right_bias / 100.0
                adjusted_pos = min(1.0, relative_pos * (1.0 + stretch_factor))

            return initial_position + adjusted_pos * right_range

    except (ValueError, OverflowError, ZeroDivisionError) as e:
        logger.error(
            "v1_mapping_calculation_error",
            score=score,
            initial_position=initial_position,
            left_bias=left_bias,
            right_bias=right_bias,
            error=str(e),
        )
        raise ValueError(f"V1 mapping calculation failed: {str(e)}")


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
            "description": "Unknown algorithm",
            "parameters": [],
            "formula": "N/A",
        }

    if algorithm_enum == PositionMappingAlgorithm.NONE:
        return {
            "name": "None (direct)",
            "version": "1.0",
            "description": "Direct score to position mapping without offset",
            "parameters": [],
            "formula": "position = score",
        }
    elif algorithm_enum == PositionMappingAlgorithm.V1:
        return {
            "name": "V1",
            "version": "1.0",
            "description": "Independent bidirectional offset control with proportional segment-based adjustment",
            "parameters": [
                {
                    "name": "left_bias",
                    "type": "integer",
                    "default": 0,
                    "range": [-100, 100],
                    "description": "Left side offset control: negative (towards origin), 0 (linear), positive (towards endpoints)",
                },
                {
                    "name": "right_bias",
                    "type": "integer",
                    "default": 0,
                    "range": [-100, 100],
                    "description": "Right side offset control: negative (towards origin), 0 (linear), positive (towards endpoints)",
                },
            ],
            "formula": "curve-based mapping with independent left/right control and proportional offsets",
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
        required_params = ["left_bias", "right_bias"]
        for param in required_params:
            if param not in params:
                return False

        # Validate left_bias range
        if not isinstance(params["left_bias"], (int, float)) or not (-100 <= params["left_bias"] <= 100):
            return False

        # Validate right_bias range
        if not isinstance(params["right_bias"], (int, float)) or not (-100 <= params["right_bias"] <= 100):
            return False

        return True
    else:
        return False

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
K = 45  # Nonlinear coefficient for V1 logarithmic mapping, adjustable for tuning
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

    Maps score to position space [0, 1000] with initial_position as origin.
    Left and right segments use mirrored calculation with independent sensitivity control.
    Uses logarithmic function for nonlinear acceleration near threshold.

    Algorithm steps:
    0. Clamp score to [0, 1000] position axis
    1. Calculate threshold based on sensitivity parameter
    2. Handle special case: threshold <= 0 → full offset
    3. Calculate normalized distance from origin
    4. Handle special case: normalized_distance >= threshold → full offset
    5. Calculate nonlinear offset using logarithmic function
    6. Map back to original space

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
    score_clamped = max(0.0, min(1000.0, score))
    ip = max(0.0, min(1000.0, initial_position))

    # Handle edge cases where ip is at boundaries
    # When ip=0, only right side exists; when ip=1000, only left side exists
    # In these cases, no meaningful offset can be calculated, return original score
    if ip <= EPSILON:
        return score_clamped
    if ip >= 1000.0 - EPSILON:
        return score_clamped

    # Handle special case: score equals ip (at origin point)
    # No offset needed, return ip directly
    if abs(score_clamped - ip) < EPSILON:
        return ip

    # Step 1: Determine segment and calculate threshold
    if score_clamped < ip:
        # Left segment: [0, ip]
        sensitivity = left_sensitivity
        space = ip
        is_left = True
    else:
        # Right segment: [ip, 1000]
        sensitivity = right_sensitivity
        space = 1000.0 - ip
        is_left = False

    # Calculate threshold from sensitivity (unified formula for both segments)
    # sensitivity = 100 → threshold = 0.0 (most sensitive, any distance triggers full offset)
    # sensitivity = 0 → threshold = 1.0 (standard behavior)
    # sensitivity = -100 → threshold = 2.0 (least sensitive, rarely triggers offset)
    threshold = 1.0 - sensitivity / 100.0

    # Step 2: Handle threshold <= 0 case (full offset to boundary)
    if threshold <= EPSILON:
        offset_ratio = 1.0
    else:
        # Step 3: Calculate normalized distance from origin
        if is_left:
            normalized_distance = (ip - score_clamped) / ip
        else:
            normalized_distance = (score_clamped - ip) / (1000.0 - ip)

        # Step 4: Handle normalized_distance >= threshold case (beyond threshold, full offset)
        if normalized_distance >= threshold:
            offset_ratio = 1.0
        else:
            # Step 5: Calculate nonlinear offset using logarithmic function
            ratio = normalized_distance / threshold

            # Numerical stability: avoid log(0) when ratio approaches 1
            if ratio >= 1.0 - EPSILON:
                offset_ratio = 1.0
            else:
                # offset_ratio = -K * LN(1 - ratio) / 100
                # As ratio → 1, LN(1-ratio) → -∞, so -LN(1-ratio) → +∞
                # This creates acceleration effect near threshold
                offset_ratio = -K * math.log(1.0 - ratio) / 100.0

                # Clamp offset_ratio to [0, 1] to prevent overflow
                offset_ratio = max(0.0, min(1.0, offset_ratio))

    # Step 6: Map back to original space
    if is_left:
        position = ip - space * offset_ratio
    else:
        position = ip + space * offset_ratio

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
            "version": "5.0",
            "description": "Nonlinear position mapping with sensitivity-controlled logarithmic offset. Uses fixed space mapping with mirrored left/right calculation, monotonically increasing, nonlinear acceleration near threshold.",
            "parameters": [
                {
                    "name": "left_sensitivity",
                    "type": "integer",
                    "default": 0,
                    "range": [-100, 100],
                    "description": "Left segment sensitivity control: 100 (most sensitive) to -100 (least sensitive)",
                },
                {
                    "name": "right_sensitivity",
                    "type": "integer",
                    "default": 0,
                    "range": [-100, 100],
                    "description": "Right segment sensitivity control: 100 (most sensitive) to -100 (least sensitive)",
                },
            ],
            "formula": "threshold = 1 - sensitivity/100; ratio = normalized_distance / threshold; if ratio < 1: offset_ratio = -K*ln(1-ratio)/100; position = ip ± space*offset_ratio",
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
        # Validate left_sensitivity and right_sensitivity parameters
        required_params = ["left_sensitivity", "right_sensitivity"]
        for param in required_params:
            if param not in params:
                return False

        # Validate left_sensitivity range
        if not isinstance(params["left_sensitivity"], (int, float)) or not (-100 <= params["left_sensitivity"] <= 100):
            return False

        # Validate right_sensitivity range
        if not isinstance(params["right_sensitivity"], (int, float)) or not (-100 <= params["right_sensitivity"] <= 100):
            return False

        return True
    else:
        return False

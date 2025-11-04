"""
Score mapping utilities.

This module provides pure helpers to map arbitrary score ranges to the
normalized 0-1000 permille scale used by relationship selection.

All functions are stateless and raise ValueError on invalid inputs so that
callers can decide whether to short-circuit selection and return empty.
"""

from utils.logging import get_logger

logger = get_logger(__name__)


def map_to_permille(value: float, min_value: float, max_value: float) -> float:
    """
    Map a value from [min_value, max_value] to [0, 1000].

    Args:
        value: Original score value
        min_value: Range minimum (must be <= max_value)
        max_value: Range maximum (must be >= min_value)

    Returns:
        A float in [0, 1000]

    Raises:
        ValueError: If min/max are invalid or min == max
    """
    try:
        if min_value is None or max_value is None:
            raise ValueError("range_min_or_max_missing")
        if not isinstance(min_value, (int, float)) or not isinstance(max_value, (int, float)):
            raise ValueError("range_min_or_max_invalid_type")
        if min_value == max_value:
            raise ValueError("range_min_equals_max")
        if min_value > max_value:
            raise ValueError("range_min_greater_than_max")

        # Normalize value to [0,1]
        ratio = (float(value) - float(min_value)) / (float(max_value) - float(min_value))
        # Clamp to [0,1]
        if ratio < 0.0:
            ratio = 0.0
        elif ratio > 1.0:
            ratio = 1.0

        return ratio * 1000.0
    except Exception as e:
        # Log and re-raise so that callers can decide to return empty relation
        logger.error(
            "score_mapping_failed",
            value=value,
            min_value=min_value,
            max_value=max_value,
            error=str(e),
        )
        raise

"""
Calculation utilities for admin services.
Pure functions for mathematical calculations and data processing.
"""

from typing import Dict, Any, List
from services.ai.utils.score_algorithm import apply_score_algorithm


def calculate_batch_algorithm_results(
    algorithm: int, initial_position: float, params: Dict[str, Any], score_range: List[int], step: int
) -> List[Dict[str, Any]]:
    """
    Calculate batch algorithm results for a range of scores.

    Args:
        algorithm: Algorithm type
        initial_position: Initial position
        params: Algorithm parameters
        score_range: [min_score, max_score]
        step: Step size for score iteration

    Returns:
        List of calculation results
    """
    results = []

    for test_score in range(score_range[0], score_range[1] + 1, step):
        try:
            new_score = apply_score_algorithm(
                algorithm=algorithm,
                score=float(test_score),
                initial_position=initial_position,
                params=params,
            )

            results.append(
                {
                    "input_score": test_score,
                    "output_score": new_score,
                    "offset": new_score - test_score,
                }
            )

        except Exception:
            # Skip failed calculations
            results.append(
                {
                    "input_score": test_score,
                    "output_score": None,
                    "offset": None,
                    "error": "Calculation failed",
                }
            )

    return results


def calculate_algorithm_details(
    score: float, initial_position: float, new_score: float, params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate detailed algorithm information.

    Args:
        score: Input score
        initial_position: Initial position
        new_score: Output score
        params: Algorithm parameters

    Returns:
        Calculation details
    """
    direction = score - initial_position
    normalized_direction = direction / 500.0 if initial_position != 0 else 0
    offset = new_score - score

    return {
        "direction": direction,
        "normalized_direction": normalized_direction,
        "curve_factor": params.get("strength", 0.5),
        "curved_offset": offset,
    }


def calculate_performance_metrics(
    response_times: List[float],
    success_count: int,
    total_count: int,
    token_usage_list: List[Dict[str, int]],
) -> Dict[str, Any]:
    """
    Calculate performance metrics from test results.

    Args:
        response_times: List of response times in milliseconds
        success_count: Number of successful requests
        total_count: Total number of requests
        token_usage_list: List of token usage data

    Returns:
        Performance metrics
    """
    if not response_times:
        return {
            "avg_response_time": 0,
            "min_response_time": 0,
            "max_response_time": 0,
            "success_rate": 0.0,
            "total_tokens": 0,
        }

    # Calculate response time metrics
    avg_response_time = sum(response_times) / len(response_times)
    min_response_time = min(response_times)
    max_response_time = max(response_times)

    # Calculate success rate
    success_rate = success_count / total_count if total_count > 0 else 0.0

    # Calculate total tokens
    total_tokens = sum(
        usage.get("total_tokens", 0) for usage in token_usage_list if isinstance(usage, dict)
    )

    return {
        "avg_response_time": round(avg_response_time, 2),
        "min_response_time": min_response_time,
        "max_response_time": max_response_time,
        "success_rate": round(success_rate, 3),
        "total_tokens": total_tokens,
    }


def format_test_case_result(
    test_case: Dict[str, Any],
    success: bool,
    response: Any,
    response_time_ms: float,
    token_usage: Dict[str, int],
    error: str = None,
) -> Dict[str, Any]:
    """
    Format individual test case result.

    Args:
        test_case: Original test case
        success: Whether the test succeeded
        response: LLM response
        response_time_ms: Response time in milliseconds
        token_usage: Token usage statistics
        error: Error message if failed

    Returns:
        Formatted test case result
    """
    result = {
        "name": test_case.get("name", "Unknown Test"),
        "success": success,
        "response_time_ms": round(response_time_ms, 2),
    }

    if success:
        result["response"] = response
        result["token_usage"] = token_usage
    else:
        result["error"] = error or "Unknown error"
        result["response"] = None
        result["token_usage"] = {}

    return result

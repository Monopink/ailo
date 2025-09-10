"""
Validation utilities for admin API requests.
Pure functions for parameter validation.
"""

from typing import Dict, Any, List, Optional


def validate_chat_test_request(
    character_qiao_id: str, user_qiao_id: str, llm_config_key: str, test_message: str
) -> List[str]:
    """
    Validate AI chat test request parameters.

    Args:
        character_qiao_id: Character's qiao_id
        user_qiao_id: Test user's qiao_id
        llm_config_key: LLM configuration key
        test_message: Test message content

    Returns:
        List of validation error messages
    """
    errors = []

    if not character_qiao_id or not character_qiao_id.strip():
        errors.append("character_qiao_id is required")

    if not user_qiao_id or not user_qiao_id.strip():
        errors.append("user_qiao_id is required")

    if not llm_config_key or not llm_config_key.strip():
        errors.append("llm_config_key is required")

    if not test_message or not test_message.strip():
        errors.append("test_message is required")
    elif len(test_message.strip()) > 1000:
        errors.append("test_message must be less than 1000 characters")

    return errors


def validate_algorithm_test_request(
    algorithm: int, score: float, initial_position: float, params: Dict[str, Any]
) -> List[str]:
    """
    Validate algorithm test request parameters.

    Args:
        algorithm: Algorithm type
        score: Input score
        initial_position: Initial position
        params: Algorithm parameters

    Returns:
        List of validation error messages
    """
    errors = []

    # Validate algorithm type
    if algorithm not in [1, 2]:  # Assuming 1=Linear, 2=Non-linear
        errors.append("algorithm must be 1 (Linear) or 2 (Non-linear)")

    # Validate score range
    if not (0 <= score <= 1000):
        errors.append("score must be between 0 and 1000")

    # Validate initial position range
    if not (0 <= initial_position <= 1000):
        errors.append("initial_position must be between 0 and 1000")

    # Validate algorithm parameters
    if not isinstance(params, dict):
        errors.append("params must be a dictionary")
    else:
        # Validate strength parameter for non-linear algorithm
        if algorithm == 2:
            strength = params.get("strength")
            if strength is None:
                errors.append("strength parameter is required for non-linear algorithm")
            elif not isinstance(strength, (int, float)):
                errors.append("strength parameter must be a number")
            elif not (0 <= strength <= 1):
                errors.append("strength parameter must be between 0 and 1")

    return errors


def validate_batch_test_config(batch_test: Optional[Dict[str, Any]]) -> List[str]:
    """
    Validate batch test configuration.

    Args:
        batch_test: Batch test configuration

    Returns:
        List of validation error messages
    """
    errors = []

    if batch_test is None:
        return errors

    if not isinstance(batch_test, dict):
        errors.append("batch_test must be a dictionary")
        return errors

    # Validate enabled flag
    enabled = batch_test.get("enabled", False)
    if not isinstance(enabled, bool):
        errors.append("batch_test.enabled must be a boolean")

    if enabled:
        # Validate score range
        score_range = batch_test.get("score_range", [0, 1000])
        if not isinstance(score_range, list) or len(score_range) != 2:
            errors.append("batch_test.score_range must be a list of two numbers")
        elif not all(isinstance(x, (int, float)) for x in score_range):
            errors.append("batch_test.score_range values must be numbers")
        elif score_range[0] >= score_range[1]:
            errors.append("batch_test.score_range[0] must be less than score_range[1]")
        elif not (0 <= score_range[0] <= 1000) or not (0 <= score_range[1] <= 1000):
            errors.append("batch_test.score_range values must be between 0 and 1000")

        # Validate step
        step = batch_test.get("step", 50)
        if not isinstance(step, (int, float)):
            errors.append("batch_test.step must be a number")
        elif step <= 0:
            errors.append("batch_test.step must be greater than 0")
        elif step > 100:
            errors.append("batch_test.step must be less than or equal to 100")

    return errors


def validate_llm_test_request(config_keys: List[str], test_cases: List[Dict[str, Any]]) -> List[str]:
    """
    Validate LLM test request parameters.

    Args:
        config_keys: List of LLM configuration keys
        test_cases: List of test cases

    Returns:
        List of validation error messages
    """
    errors = []

    # Validate config keys
    if not config_keys or not isinstance(config_keys, list):
        errors.append("config_keys must be a non-empty list")
    elif not all(isinstance(key, str) and key.strip() for key in config_keys):
        errors.append("all config_keys must be non-empty strings")

    # Validate test cases
    if not test_cases or not isinstance(test_cases, list):
        errors.append("test_cases must be a non-empty list")
    else:
        for i, test_case in enumerate(test_cases):
            if not isinstance(test_case, dict):
                errors.append(f"test_cases[{i}] must be a dictionary")
                continue

            # Validate required fields
            name = test_case.get("name")
            if not name or not isinstance(name, str):
                errors.append(f"test_cases[{i}].name is required and must be a string")

            prompt = test_case.get("prompt")
            if not prompt or not isinstance(prompt, str):
                errors.append(f"test_cases[{i}].prompt is required and must be a string")
            elif len(prompt) > 2000:
                errors.append(f"test_cases[{i}].prompt must be less than 2000 characters")

            expected_type = test_case.get("expected_type")
            if expected_type and expected_type not in ["string", "json"]:
                errors.append(f"test_cases[{i}].expected_type must be 'string' or 'json'")

    return errors

"""
Template utilities for AI services.

This module provides utility functions for working with AI templates,
including placeholder interpolation and validation.
"""

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.models.ai import AIPersonalityPlaceholder
from app.utils.logging import get_logger

logger = get_logger(__name__)


def interpolate_prompt_template(
    template: str,
    variables: dict[str, Any],
    placeholders: list[AIPersonalityPlaceholder] | None = None,
) -> str:
    """
    Interpolate variables into a prompt template.

    Args:
        template: The prompt template containing {{variable}} placeholders
        variables: Dict of variable values to interpolate
        placeholders: Optional list of AIPersonalityPlaceholder objects for validation

    Returns:
        The interpolated prompt string
    """
    try:
        # Add system placeholders
        system_vars = _get_system_variables()
        all_vars = {**variables, **system_vars}

        # Validate required placeholders if provided
        if placeholders:
            _validate_required_placeholders(all_vars, placeholders)

        # Do the interpolation
        result = template
        for key, value in all_vars.items():
            placeholder = "{{" + key + "}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))

        return result

    except Exception as e:
        logger.error("template_interpolation_error", error=str(e))
        raise ValueError(f"Failed to interpolate template: {e!s}")


def _get_system_variables() -> dict[str, Any]:
    """Get system-level template variables."""
    now = datetime.now(ZoneInfo("Asia/Shanghai"))

    return {
        "current_datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        # Add other system variables here
    }


def _validate_required_placeholders(
    variables: dict[str, Any], placeholders: list[AIPersonalityPlaceholder]
) -> None:
    """
    Validate that all required placeholders have values.

    Args:
        variables: Dict of variable values
        placeholders: List of placeholder objects

    Raises:
        ValueError: If any required placeholder is missing
    """
    for placeholder in placeholders:
        if placeholder.is_required and placeholder.placeholder_key not in variables:
            raise ValueError(f"Missing required placeholder: {placeholder.placeholder_key}")


def interpolate_advanced_template(
    template: str,
    variables: dict[str, Any],
    placeholders: list[AIPersonalityPlaceholder] | None = None,
    max_depth: int = 3,
) -> str:
    """
    Advanced template interpolation with conditional and nested placeholder support.

    Supports:
    - Conditional placeholders: {{if:condition}}content{{/if}}
    - Nested placeholders: {{outer:{{inner}}}}
    - Default values: {{variable|default_value}}

    Args:
        template: The prompt template with advanced placeholders
        variables: Dict of variable values to interpolate
        placeholders: Optional list of AIPersonalityPlaceholder objects
        max_depth: Maximum nesting depth for recursive interpolation

    Returns:
        The interpolated prompt string

    Raises:
        ValueError: If interpolation fails or max depth exceeded
    """
    try:
        # Add system placeholders
        system_vars = _get_system_variables()
        all_vars = {**variables, **system_vars}

        # Validate required placeholders if provided
        if placeholders:
            _validate_required_placeholders(all_vars, placeholders)

        # Process template with advanced features
        result = _process_conditional_placeholders(template, all_vars)
        result = _process_nested_placeholders(result, all_vars, max_depth)
        result = _process_default_placeholders(result, all_vars)

        logger.debug(
            "advanced_template_interpolation_completed",
            template_length=len(template),
            result_length=len(result),
            variables_count=len(all_vars),
        )

        return result

    except Exception as e:
        logger.error("advanced_template_interpolation_error", error=str(e))
        raise ValueError(f"Failed to interpolate advanced template: {e!s}")


def _process_conditional_placeholders(template: str, variables: dict[str, Any]) -> str:
    """
    Process conditional placeholders in format {{if:condition}}content{{/if}}.

    Args:
        template: Template string
        variables: Variable values

    Returns:
        Template with conditional placeholders processed
    """
    try:
        # Pattern for conditional blocks: {{if:variable}}content{{/if}}
        conditional_pattern = r"\{\{if:([^}]+)\}\}(.*?)\{\{/if\}\}"

        def replace_conditional(match):
            condition_var = match.group(1).strip()
            content = match.group(2)

            # Check if condition variable exists and is truthy
            condition_value = variables.get(condition_var)
            if condition_value and str(condition_value).strip():
                return content
            return ""

        result = re.sub(conditional_pattern, replace_conditional, template, flags=re.DOTALL)

        logger.debug(
            "conditional_placeholders_processed",
            original_length=len(template),
            result_length=len(result),
        )

        return result

    except Exception as e:
        logger.error("conditional_placeholder_processing_failed", error=str(e))
        return template


def _process_nested_placeholders(
    template: str, variables: dict[str, Any], max_depth: int, current_depth: int = 0
) -> str:
    """
    Process nested placeholders recursively.

    Args:
        template: Template string
        variables: Variable values
        max_depth: Maximum recursion depth
        current_depth: Current recursion depth

    Returns:
        Template with nested placeholders processed
    """
    try:
        if current_depth >= max_depth:
            logger.warning(
                "nested_placeholder_max_depth_reached",
                max_depth=max_depth,
                current_depth=current_depth,
            )
            return template

        # Find nested placeholders pattern: {{outer:{{inner}}}}
        nested_pattern = r"\{\{([^:{}]+):\{\{([^}]+)\}\}\}\}"

        def replace_nested(match):
            outer_key = match.group(1).strip()
            inner_key = match.group(2).strip()

            # Get inner value first
            inner_value = variables.get(inner_key, "")

            # Construct new key from outer + inner
            combined_key = f"{outer_key}:{inner_value}"
            combined_value = variables.get(combined_key, "")

            return str(combined_value)

        result = re.sub(nested_pattern, replace_nested, template)

        # If we made changes, recursively process again
        if result != template:
            result = _process_nested_placeholders(result, variables, max_depth, current_depth + 1)

        return result

    except Exception as e:
        logger.error("nested_placeholder_processing_failed", error=str(e))
        return template


def _process_default_placeholders(template: str, variables: dict[str, Any]) -> str:
    """
    Process placeholders with default values in format {{variable|default}}.

    Args:
        template: Template string
        variables: Variable values

    Returns:
        Template with default placeholders processed
    """
    try:
        # Pattern for default values: {{variable|default_value}}
        default_pattern = r"\{\{([^|}]+)\|([^}]*)\}\}"

        def replace_default(match):
            var_name = match.group(1).strip()
            default_value = match.group(2).strip()

            # Get variable value or use default
            var_value = variables.get(var_name)
            if var_value is not None and str(var_value).strip():
                return str(var_value)
            return default_value

        result = re.sub(default_pattern, replace_default, template)

        # Process remaining simple placeholders
        result = interpolate_prompt_template(result, variables)

        return result

    except Exception as e:
        logger.error("default_placeholder_processing_failed", error=str(e))
        return template

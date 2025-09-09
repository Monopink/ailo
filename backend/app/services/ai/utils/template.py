"""
Template utilities for AI services.

This module provides utility functions for working with AI templates,
including placeholder interpolation and validation.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from models.ai import AIPersonalityPlaceholder
from utils.logging import get_logger

logger = get_logger(__name__)

def interpolate_prompt_template(
    template: str,
    variables: Dict[str, Any],
    placeholders: Optional[List[AIPersonalityPlaceholder]] = None,
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
        raise ValueError(f"Failed to interpolate template: {str(e)}")

def _get_system_variables() -> Dict[str, Any]:
    """Get system-level template variables."""
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    
    return {
        "current_datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        # Add other system variables here
    }

def _validate_required_placeholders(
    variables: Dict[str, Any],
    placeholders: List[AIPersonalityPlaceholder]
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
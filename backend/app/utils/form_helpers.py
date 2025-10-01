"""
Form data helper utilities for type-safe form field extraction.

This module provides utilities to safely extract text fields from Starlette
form data, ensuring type safety and proper error handling.
"""

from starlette.datastructures import FormData, UploadFile


class FormFieldError(ValueError):
    """Exception raised when form field extraction fails."""

    pass


def get_text_field(
    form_data: FormData,
    field_name: str,
    required: bool = True,
    default: str = "",
) -> str:
    """
    Extract text field from form data with type safety.

    Args:
        form_data: Form data object from request
        field_name: Name of the field to extract
        required: Whether the field is required (default: True)
        default: Default value if field is not required and missing (default: "")

    Returns:
        Text value from the form field

    Raises:
        FormFieldError: If field is a file upload or missing when required

    Example:
        >>> form_data = await request.form()
        >>> username = get_text_field(form_data, "username")
        >>> bio = get_text_field(form_data, "bio", required=False, default="")
    """
    value = form_data.get(field_name)

    # Check if value is a file upload
    if isinstance(value, UploadFile):
        raise FormFieldError(f"{field_name} must be a text field, not a file upload")

    # Check if value is missing
    if value is None:
        if required:
            raise FormFieldError(f"Missing required field: {field_name}")
        return default

    # Return the string value
    return value


def get_int_field(
    form_data: FormData,
    field_name: str,
    required: bool = True,
    default: int = 0,
) -> int:
    """
    Extract integer field from form data with type safety.

    Args:
        form_data: Form data object from request
        field_name: Name of the field to extract
        required: Whether the field is required (default: True)
        default: Default value if field is not required and missing (default: 0)

    Returns:
        Integer value from the form field

    Raises:
        FormFieldError: If field is invalid or missing when required

    Example:
        >>> form_data = await request.form()
        >>> age = get_int_field(form_data, "age")
        >>> count = get_int_field(form_data, "count", required=False, default=10)
    """
    text_value = get_text_field(form_data, field_name, required=required, default=str(default))

    try:
        return int(text_value)
    except ValueError:
        raise FormFieldError(f"{field_name} must be a valid integer, got: {text_value}")


def get_float_field(
    form_data: FormData,
    field_name: str,
    required: bool = True,
    default: float = 0.0,
) -> float:
    """
    Extract float field from form data with type safety.

    Args:
        form_data: Form data object from request
        field_name: Name of the field to extract
        required: Whether the field is required (default: True)
        default: Default value if field is not required and missing (default: 0.0)

    Returns:
        Float value from the form field

    Raises:
        FormFieldError: If field is invalid or missing when required

    Example:
        >>> form_data = await request.form()
        >>> temperature = get_float_field(form_data, "temperature")
        >>> rate = get_float_field(form_data, "rate", required=False, default=0.5)
    """
    text_value = get_text_field(form_data, field_name, required=required, default=str(default))

    try:
        return float(text_value)
    except ValueError:
        raise FormFieldError(f"{field_name} must be a valid float, got: {text_value}")

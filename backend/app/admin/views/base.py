"""
Base role-aware ModelView for Starlette-Admin.

Provides unified create/edit/delete permissions based on admin role.
"""

from typing import Any, List
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import EnumField

from enums import AdminRole


def convert_empty_strings_to_none(obj: Any, field_names: List[str]) -> None:
    """
    Convert empty string values to None for specified fields.

    This is essential for fields with unique constraints in the database,
    as NULL values don't count as duplicates but empty strings do.

    Args:
        obj: The model object to modify
        field_names: List of field names to check and convert

    Example:
        convert_empty_strings_to_none(user_obj, ["phone", "email", "wechat_openid"])
    """
    for field_name in field_names:
        if hasattr(obj, field_name):
            value = getattr(obj, field_name)
            if value == "":
                setattr(obj, field_name, None)


def _get_admin_role(request: Request) -> int | None:
    """Extract admin role from session. Returns int value or None."""
    admin_user = request.session.get("admin_user") if hasattr(request, "session") else None
    if not admin_user:
        return None
    role = admin_user.get("role")
    # AdminRole may be stored as enum or int; normalize to int
    try:
        return int(role) if role is not None else None
    except Exception:
        return None


class IntegerEnumField(EnumField):
    """
    EnumField that properly handles integer values for database storage.

    Starlette-admin's default EnumField returns strings from forms,
    but database INTEGER fields need actual integers. This field converts:
    - Form input (string) → Database (int)
    - Database (int) → Form display (string for selection)

    Usage:
        IntegerEnumField("status", enum=UserStatus)
        IntegerEnumField("status", choices=[(1, "Active"), (2, "Inactive")])
    """

    def __init__(
        self,
        name: str,
        enum: Any = None,
        choices: Any = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize IntegerEnumField.

        Args:
            name: Field name
            enum: IntEnum class (will be converted to choices)
            choices: List of (int_value, display_label) tuples (alternative to enum)
            **kwargs: Additional field arguments
        """
        # Store enum for later use in serialize_value
        self._enum = enum

        # Convert IntEnum to choices if provided
        if enum is not None:
            choices = [(member.value, member.name.replace("_", " ").title()) for member in enum]
        elif choices is None:
            raise ValueError("Either 'enum' or 'choices' must be provided")

        super().__init__(name, choices=choices, **kwargs)

    async def parse_form_data(self, request: Request, form_data: Any, action: Any) -> Any:
        """
        Parse form data, converting string to integer.

        Args:
            request: Request object
            form_data: Form data (usually string from select)
            action: Action type (create/edit)

        Returns:
            Integer value for database storage, or None if empty/invalid

        Raises:
            ValueError: If conversion fails (invalid integer format)
        """
        value = await super().parse_form_data(request, form_data, action)

        # Handle None or empty string (valid for optional fields)
        if value is None or value == "":
            return None

        # Convert string to integer - let exceptions propagate
        return int(value)

    async def serialize_value(self, request: Request, value: Any, action: Any) -> Any:
        """
        Serialize database value for display.

        Args:
            request: Request object
            value: Database value (integer or string representation of integer)
            action: Action type (RequestAction enum: LIST/DETAIL/EDIT/CREATE)

        Returns:
            For LIST/DETAIL: enum name (e.g., "Male") or None for invalid values
            For EDIT/CREATE: integer value for form selection (e.g., 1)
        """
        if value is None or value == "":
            return None

        # Convert string to int if needed (for VARCHAR fields storing integers)
        if isinstance(value, str):
            try:
                value = int(value)
            except (ValueError, TypeError):
                # Invalid string value, return None to display as -null-
                return None

        # Import RequestAction for comparison
        from starlette_admin._types import RequestAction

        # For list and detail views, show friendly label from choices
        # action is RequestAction enum, compare directly with enum values
        if action in (RequestAction.LIST, RequestAction.DETAIL):
            if self.choices is not None:
                for choice_value, choice_label in self.choices:
                    if choice_value == value:
                        return choice_label
            # Value not in enum definition, return None to display as -null-
            return None

        # For edit/create forms, return integer value for form selection
        # This ensures the form correctly matches the value with select options
        return int(value) if value is not None else None


class BaseRoleAwareModelView(ModelView):
    """ModelView with role-based write permissions.

    Policy:
    - SUPER_ADMIN: full access (create/edit/delete)
    - ADMIN: default allow (can be further restricted per view)
    - VIEWER: read-only (no create/edit/delete)
    """

    def can_create(self, request: Request) -> bool:  # type: ignore[override]
        role = _get_admin_role(request)
        if role is None:
            return False
        if role == AdminRole.VIEWER:
            return False
        return True

    def can_edit(self, request: Request) -> bool:  # type: ignore[override]
        role = _get_admin_role(request)
        if role is None:
            return False
        if role == AdminRole.VIEWER:
            return False
        return True

    def can_delete(self, request: Request) -> bool:  # type: ignore[override]
        role = _get_admin_role(request)
        if role is None:
            return False
        if role == AdminRole.VIEWER:
            return False
        return True

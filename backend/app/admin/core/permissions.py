"""
Simplified permission system for admin module.
Uses role-based permissions instead of complex database relationships.
"""

from functools import wraps
from typing import List

from fastapi import HTTPException
from admin.models.admin import AdminUser, AdminRole


def require_permissions(permissions: List[str]):
    """
    Decorator to check if admin user has required permissions.

    Args:
        permissions: List of required permissions

    Usage:
        @require_permissions(['view_users'])
        async def get_users(current_admin: AdminUser = Depends(GetAdminUser)):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current admin user from kwargs - try different parameter names
            current_admin = kwargs.get("current_admin") or kwargs.get("admin_user")

            if not current_admin:
                raise HTTPException(status_code=401, detail="Authentication required")

            if not isinstance(current_admin, AdminUser):
                raise HTTPException(status_code=401, detail="Invalid user type")

            # Check if user is active
            if not current_admin.is_active:
                raise HTTPException(status_code=403, detail="Account is disabled")

            # Check permissions
            for permission in permissions:
                if not current_admin.has_permission(permission):
                    raise HTTPException(status_code=403, detail=f"Permission denied: requires {permission}")

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_super_admin(func):
    """
    Decorator to require super admin role.

    Usage:
        @require_super_admin
        async def delete_user(current_admin: AdminUser = Depends(GetAdminUser)):
            pass
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Get current admin user from kwargs - try different parameter names
        current_admin = kwargs.get("current_admin") or kwargs.get("admin_user")

        if not current_admin:
            raise HTTPException(status_code=401, detail="Authentication required")

        if not isinstance(current_admin, AdminUser):
            raise HTTPException(status_code=401, detail="Invalid user type")

        if not current_admin.is_super_admin():
            raise HTTPException(status_code=403, detail="Super admin role required")

        return await func(*args, **kwargs)

    return wrapper


def require_role(required_role: str):
    """
    Decorator to check if admin user has specific role.

    Args:
        required_role: Required role ('super_admin', 'admin', 'viewer')

    Usage:
        @require_role('admin')
        async def create_bot(current_admin: AdminUser = Depends(GetAdminUser)):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current admin user from kwargs - try different parameter names
            current_admin = kwargs.get("current_admin") or kwargs.get("admin_user")

            if not current_admin:
                raise HTTPException(status_code=401, detail="Authentication required")

            if not isinstance(current_admin, AdminUser):
                raise HTTPException(status_code=401, detail="Invalid user type")

            if not current_admin.is_active:
                raise HTTPException(status_code=403, detail="Account is disabled")

            # Check role hierarchy
            role_hierarchy = {
                AdminRole.VIEWER.value: 1,
                AdminRole.ADMIN.value: 2,
                AdminRole.SUPER_ADMIN.value: 3,
            }

            user_level = role_hierarchy.get(current_admin.role, 0)
            required_level = role_hierarchy.get(required_role, 999)

            if user_level < required_level:
                raise HTTPException(
                    status_code=403, detail=f"Permission denied: requires {required_role} role"
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Convenience decorators for common permission checks
def require_admin_or_above(func):
    """Require admin or super_admin role"""
    return require_role("admin")(func)


def require_view_permission(func):
    """Require view permission (all roles can view)"""
    return require_role("viewer")(func)


def require_modify_permission(func):
    """Require modify permission (admin or super_admin)"""
    return require_role("admin")(func)


def require_delete_permission(func):
    """Require delete permission (super_admin only)"""
    return require_super_admin(func)


# Permission checking is now handled directly by AdminUser model methods
# This keeps the logic centralized and avoids duplication

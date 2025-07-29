"""
Simplified admin models module.
Contains essential admin-related database models.
"""

from .admin import AdminUser
from .logs import (
    AdminOperationLog,
    AdminLoginLog,
)

__all__ = [
    "AdminUser",
    "AdminOperationLog",
    "AdminLoginLog",
]

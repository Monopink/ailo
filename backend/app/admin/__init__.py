"""
Admin module for Says application.
Provides web-based administration interface.
"""

from .main import admin_router, create_admin_app

__all__ = ["admin_router", "create_admin_app"]

"""
Admin services module.

This module provides business logic managers and utility functions for admin operations.
All complex business logic is handled through Manager classes and pure utility functions.

Architecture:
- managers/: Business process managers (class-based)
- utils/: Pure utility functions (function-based)

Note: Basic CRUD operations (list, view, edit, delete) should be handled
by Starlette-Admin ModelView directly, not through service functions.
"""

# Managers and utils are available through their respective modules
# Import them directly from their modules when needed:
# from services.admin.managers.ai_test_manager import AITestManager
# from services.admin.utils.validation_utils import validate_chat_test_request

__all__ = []

"""
Admin services module.

This module provides specialized services for admin operations following
clean architecture principles with stateless services and clear separation of concerns.

Architecture:
- ai_character_chat/: AI character chat testing specialized service
- test_users.py: Test user management utilities

Note: Basic CRUD operations (list, view, edit, delete) should be handled
by Starlette-Admin ModelView directly, not through service functions.
"""

# Services are available through their respective modules
# Import them directly when needed:
# from services.admin.ai_character_chat import ai_character_chat_test_service
# from services.admin.test_users import TestUserService

__all__ = []

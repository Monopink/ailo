"""
Admin services module.

This module provides specialized services for admin operations following
clean architecture principles with stateless services and clear separation of concerns.

Architecture:
- data/: Data query services (dashboard stats, style dimensions)
- testing/: Testing services (LLM config, instance chat, style algorithm)
- instance_relationship.py: Instance relationship generation

Note: Basic CRUD operations (list, view, edit, delete) should be handled
by Starlette-Admin ModelView directly, not through service functions.
"""

__all__ = []

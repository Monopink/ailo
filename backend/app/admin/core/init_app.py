"""
Admin application initialization module.
Handles database initialization and default data creation.
"""

from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

from admin.settings.config import admin_settings
from utils.logging import get_logger

logger = get_logger(__name__)


def make_middlewares():
    """Create middleware list for admin application"""
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=admin_settings.CORS_ORIGINS,
            allow_credentials=admin_settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=admin_settings.CORS_ALLOW_METHODS,
            allow_headers=admin_settings.CORS_ALLOW_HEADERS,
        ),
    ]
    return middleware


def register_exceptions(app: FastAPI):
    """Register exception handlers for admin application"""
    # Use main project's exception handlers
    pass


def register_routers(app: FastAPI, prefix: str = "/api"):
    """Register admin routers"""
    from admin.api.v1 import v1_router

    app.include_router(v1_router, prefix=prefix)


async def init_admin_data():
    """
    Initialize admin data using the existing init_admin_db.py script.
    This function is a placeholder - actual initialization should be done
    by running the init_admin_db.py script.
    """
    logger.info(
        "admin_data_init", message="Admin data initialization should be done via init_admin_db.py script"
    )
    pass


# Simplified initialization functions for future use
# These are placeholders that can be implemented when needed


async def init_superuser():
    """Initialize default superuser - placeholder"""
    pass


async def init_menus():
    """Initialize default menus - placeholder"""
    pass


async def init_apis():
    """Initialize default APIs - placeholder"""
    pass


async def init_roles():
    """Initialize default roles - placeholder"""
    pass


async def init_data():
    """Initialize all admin data - placeholder"""
    await init_admin_data()

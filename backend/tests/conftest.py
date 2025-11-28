"""Pytest configuration and shared fixtures for testing."""

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / "deployment" / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Override database host for local testing
# Tests run on host machine, not in Docker, so use localhost
os.environ["POSTGRES_HOST"] = "localhost"

# Add backend/app to Python path
backend_app_path = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(backend_app_path))

from core.config import get_settings
from core.database import get_db
from main import create_app


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    settings = get_settings()

    # Use the same database as development for now
    # In production, you should use a separate test database
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        poolclass=NullPool,  # Disable connection pooling for tests
    )

    yield engine

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for each test."""
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an HTTP client for testing the API."""
    app = create_app()

    # Override the database dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_headers() -> dict[str, str]:
    """Return authentication headers for testing protected endpoints."""
    # This is a placeholder - implement actual token generation
    # based on your authentication system
    return {
        "Authorization": "Bearer test_token"
    }

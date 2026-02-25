"""Pytest configuration and shared fixtures for testing."""

import asyncio
import importlib
import os
import sys
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.utils.snowflake import init_snowflake

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

core_config = importlib.import_module("core.config")
get_settings = core_config.get_settings
core_database = importlib.import_module("core.database")
get_db = core_database.get_db
main_module = importlib.import_module("main")
create_app = main_module.create_app


@pytest.fixture(scope="session", autouse=True)
def initialize_snowflake() -> None:
    """
    Initialize Snowflake generator for all tests.

    This fixture automatically runs once per test session before any tests.
    """
    init_snowflake(datacenter_id=1, machine_id=1)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
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


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for each test."""
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an HTTP client for testing the API."""
    app = create_app()

    # Override the database dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Client-IP": "203.0.113.10"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Return authentication headers for testing protected endpoints."""
    # This is a placeholder - implement actual token generation
    # based on your authentication system
    return {"Authorization": "Bearer test_token"}

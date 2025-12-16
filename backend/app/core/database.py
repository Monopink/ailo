"""Database connection and session management."""

import asyncio
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _create_engine(settings: Settings) -> AsyncEngine:
    """Create a configured AsyncEngine for the application."""

    echo_sql = getattr(settings, "POSTGRES_ECHO", False)
    return create_async_engine(
        settings.database_url,
        echo=echo_sql,
        pool_pre_ping=False,
        pool_recycle=3600,
        pool_size=20,
        max_overflow=30,
        connect_args={
            "server_settings": {
                "jit": "off",
            }
        },
    )


@lru_cache
def get_engine() -> AsyncEngine:
    """Return cached AsyncEngine instance."""

    return _create_engine(get_settings())


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return cached session factory bound to the engine."""

    return async_sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to provide a managed database session."""

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise


async def init_database() -> None:
    """Initialize database connection with retry mechanism."""

    max_retries = 10
    retry_count = 0
    base_delay = 1
    max_delay = 30

    while True:
        try:
            logger.info("attempting_database_connection")
            session_factory = get_sessionmaker()
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
                logger.info("database_connection_test_successful")

            logger.info("database_connection_initialized")
            break
        except SQLAlchemyError as e:
            retry_count += 1
            if retry_count > max_retries:
                error_msg = f"Database initialization failed after {max_retries} attempts"
                logger.critical(
                    "database_initialization_failed", error=str(e), attempts=max_retries
                )
                raise Exception(error_msg) from e

            delay = min(base_delay * (2 ** (retry_count - 1)), max_delay)
            logger.warning(
                "database_connection_retry", attempt=retry_count, delay=delay, error=str(e)
            )
            await asyncio.sleep(delay)
        except Exception as e:
            error_msg = "Unexpected error during database initialization"
            logger.critical("unexpected_database_initialization_error", error=str(e), exc_info=True)
            raise Exception(error_msg) from e


async def close_database() -> None:
    """Close database connections."""

    try:
        await get_engine().dispose()
        logger.info("database_connections_closed")
    except Exception as e:
        logger.error("database_close_error", error=str(e), exc_info=True)


def reset_database_state() -> None:
    """Clear cached engine and session maker (useful for tests)."""

    get_sessionmaker.cache_clear()
    get_engine.cache_clear()

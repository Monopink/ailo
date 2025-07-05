"""
Database connection management.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from ..core.config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Create an async engine to connect to the database
engine = create_async_engine(settings.database_url, echo=True, pool_pre_ping=True, pool_recycle=300)

# Create a sessionmaker to generate new Session objects
SessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def init_database():
    """Initialize database connection with retry mechanism."""
    max_retries = 100
    retry_count = 0
    base_delay = 1  # Initial delay 1 second
    max_delay = 30  # Maximum delay 30 seconds

    while True:
        try:
            logger.info("attempting_database_connection")
            async with SessionLocal() as session:
                # Test connection
                await session.execute(text("SELECT 1"))
                logger.info("database_connection_test_successful")

                # Check table schema
                try:
                    # Check if bots table has all necessary columns
                    await session.execute(text("SELECT friend_score FROM bots LIMIT 1"))
                    logger.info("database_schema_validation_successful")
                except SQLAlchemyError as schema_error:
                    logger.warning(
                        "database_schema_validation_failed",
                        error=str(schema_error),
                        message="This might be expected if the database is newly created or being updated",
                    )

            logger.info("database_connection_initialized")
            break
        except SQLAlchemyError as e:
            retry_count += 1
            if retry_count > max_retries:
                error_msg = f"Database initialization failed after {max_retries} attempts"
                logger.critical("database_initialization_failed", error=str(e), attempts=max_retries)
                raise Exception(error_msg) from e

            # Calculate delay for next retry (exponential backoff)
            delay = min(base_delay * (2 ** (retry_count - 1)), max_delay)
            logger.warning("database_connection_retry", attempt=retry_count, delay=delay, error=str(e))
            await asyncio.sleep(delay)
        except Exception as e:
            error_msg = "Unexpected error during database initialization"
            logger.critical("unexpected_database_initialization_error", error=str(e), exc_info=True)
            raise Exception(error_msg) from e

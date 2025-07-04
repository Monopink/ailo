"""
Database connection management.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from ..core.config import settings

# Create an async engine to connect to the database
engine = create_async_engine(settings.database_url, echo=True, pool_pre_ping=True)

# Create a sessionmaker to generate new Session objects
SessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False
)

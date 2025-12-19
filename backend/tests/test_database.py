"""Test database connectivity and basic operations."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_database_connection(db_session: AsyncSession):
    """Test that database connection works."""
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_database_version(db_session: AsyncSession):
    """Test that PostgreSQL version can be retrieved."""
    result = await db_session.execute(text("SELECT version()"))
    version = result.scalar()

    assert version is not None
    assert "PostgreSQL" in version


@pytest.mark.asyncio
async def test_database_current_database(db_session: AsyncSession):
    """Test that we're connected to the correct database."""
    result = await db_session.execute(text("SELECT current_database()"))
    db_name = result.scalar()

    assert db_name == "ailo"


@pytest.mark.asyncio
async def test_database_tables_exist(db_session: AsyncSession):
    """Test that essential tables exist in the database."""
    # Check if users table exists
    result = await db_session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'users'
            )
            """
        )
    )
    users_table_exists = result.scalar()

    assert users_table_exists is True, "Users table should exist"

    # Check if system_configs table exists
    result = await db_session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'system_configs'
            )
            """
        )
    )
    configs_table_exists = result.scalar()

    assert configs_table_exists is True, "System configs table should exist"

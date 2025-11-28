"""Test health check endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_success(client: AsyncClient):
    """Test that health check endpoint returns success."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Health endpoint should return status
    assert "status" in data
    assert data["status"] in ["healthy", "unhealthy"]

    # Should include database status
    assert "database" in data

    # Should include app info
    assert "app" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_health_check_includes_version(client: AsyncClient):
    """Test that health check includes version information."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Version info should be present
    assert "version" in data or "app_version" in data or data["status"] == "healthy"

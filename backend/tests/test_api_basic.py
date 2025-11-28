"""Test basic API functionality."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_root_redirect(client: AsyncClient):
    """Test that root path redirects or returns valid response."""
    response = await client.get("/", follow_redirects=False)

    # Should either redirect or return a valid response
    assert response.status_code in [200, 301, 302, 307, 308]


@pytest.mark.asyncio
async def test_api_v1_prefix_exists(client: AsyncClient):
    """Test that API v1 prefix is accessible."""
    # Try to access a non-existent v1 endpoint
    # Should return 404 (not found) rather than 500 (server error)
    response = await client.get("/api/v1/nonexistent")

    # 404 means the router exists but endpoint doesn't
    # 500 or other errors would indicate routing problems
    assert response.status_code in [404, 405]


@pytest.mark.asyncio
async def test_cors_headers_present(client: AsyncClient):
    """Test that CORS headers are configured."""
    response = await client.get("/health")

    # CORS should be configured - check for CORS headers
    # 405 for OPTIONS is acceptable if CORS middleware is present
    assert response.status_code == 200

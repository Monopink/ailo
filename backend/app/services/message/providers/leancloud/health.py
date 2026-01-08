"""
LeanCloud service health check.

Provides health check functionality for LeanCloud messaging service.
"""

import httpx

from app.utils.logging import get_logger

HTTP_OK = 200
DEFAULT_HEALTH_TIMEOUT = 5.0

logger = get_logger(__name__)


async def check_leancloud_health(
    app_id: str,
    master_key: str,
    base_url: str,
    health_timeout: float = DEFAULT_HEALTH_TIMEOUT,
) -> tuple[bool, str | None]:
    """
    Check LeanCloud service health.

    Uses the /1.1/date endpoint which is lightweight and reliable for health checks.
    This endpoint returns the current server time and requires minimal processing.

    Args:
        app_id: LeanCloud App ID
        master_key: LeanCloud Master Key
        base_url: LeanCloud base URL
        health_timeout: Request timeout in seconds (default: 5.0)

    Returns:
        Tuple of (is_healthy, error_message)
        - is_healthy: True if service is accessible and responding correctly
        - error_message: Error description if unhealthy, None if healthy

    Example:
        >>> is_healthy, error = await check_leancloud_health(
        ...     app_id="xxx",
        ...     master_key="yyy",
        ...     base_url="https://example.com"
        ... )
        >>> if not is_healthy:
        ...     logger.error("LeanCloud unhealthy", error=error)
    """
    result: tuple[bool, str | None] = (False, None)
    try:
        # Use /1.1/date endpoint for health check
        # This is a lightweight endpoint that returns server time
        url = f"{base_url}/1.1/date"
        headers = {
            "X-LC-Id": app_id,
            "X-LC-Key": f"{master_key},master",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=health_timeout) as client:
            response = await client.get(url, headers=headers)

        if response.status_code == HTTP_OK:
            logger.debug("leancloud_health_check_passed")
            result = (True, None)
        else:
            error_msg = f"API returned status {response.status_code}"
            logger.warning(
                "leancloud_health_check_failed",
                status=response.status_code,
                response_text=response.text[:200],  # Log first 200 chars
            )
            result = (False, error_msg)

    except TimeoutError:
        error_msg = f"Connection timeout ({health_timeout}s)"
        logger.warning("leancloud_health_check_timeout", timeout=health_timeout)
        result = (False, error_msg)

    except httpx.TimeoutException:
        error_msg = "Connection timeout (HTTP client)"
        logger.warning("leancloud_health_check_timeout", timeout=health_timeout)
        result = (False, error_msg)

    except httpx.ConnectError as e:
        error_msg = f"Connection error: {e!s}"
        logger.warning("leancloud_health_check_connection_error", error=str(e))
        result = (False, error_msg)

    except httpx.HTTPError as e:
        error_msg = f"HTTP error: {e!s}"
        logger.warning("leancloud_health_check_http_error", error=str(e))
        result = (False, error_msg)

    except Exception as e:
        error_msg = f"Unexpected error: {e!s}"
        logger.error(
            "leancloud_health_check_error", error=str(e), error_type=type(e).__name__, exc_info=True
        )
        result = (False, error_msg)

    return result

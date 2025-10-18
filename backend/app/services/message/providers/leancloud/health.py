"""
LeanCloud service health check.

Provides health check functionality for LeanCloud messaging service.
"""

import httpx
from typing import Optional

from utils.logging import get_logger

logger = get_logger(__name__)


async def check_leancloud_health(
    app_id: str,
    master_key: str,
    base_url: str,
    timeout: float = 5.0
) -> tuple[bool, Optional[str]]:
    """
    Check LeanCloud service health.

    Uses the /1.1/date endpoint which is lightweight and reliable for health checks.
    This endpoint returns the current server time and requires minimal processing.

    Args:
        app_id: LeanCloud App ID
        master_key: LeanCloud Master Key
        base_url: LeanCloud base URL (e.g., https://xxx.lc-cn-n1-shared.com)
        timeout: Request timeout in seconds (default: 5.0)

    Returns:
        Tuple of (is_healthy, error_message)
        - is_healthy: True if service is accessible and responding correctly
        - error_message: Error description if unhealthy, None if healthy

    Example:
        >>> is_healthy, error = await check_leancloud_health(
        ...     app_id="xxx",
        ...     master_key="yyy",
        ...     base_url="https://xxx.lc-cn-n1-shared.com"
        ... )
        >>> if not is_healthy:
        ...     logger.error("LeanCloud unhealthy", error=error)
    """
    try:
        # Use /1.1/date endpoint for health check
        # This is a lightweight endpoint that returns server time
        url = f"{base_url}/1.1/date"
        headers = {
            "X-LC-Id": app_id,
            "X-LC-Key": f"{master_key},master",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                logger.debug("leancloud_health_check_passed")
                return True, None
            else:
                error_msg = f"API returned status {response.status_code}"
                logger.warning(
                    "leancloud_health_check_failed",
                    status=response.status_code,
                    response_text=response.text[:200]  # Log first 200 chars
                )
                return False, error_msg

    except httpx.TimeoutException:
        error_msg = f"Connection timeout ({timeout}s)"
        logger.warning("leancloud_health_check_timeout", timeout=timeout)
        return False, error_msg

    except httpx.ConnectError as e:
        error_msg = f"Connection error: {str(e)}"
        logger.warning("leancloud_health_check_connection_error", error=str(e))
        return False, error_msg

    except httpx.HTTPError as e:
        error_msg = f"HTTP error: {str(e)}"
        logger.warning("leancloud_health_check_http_error", error=str(e))
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(
            "leancloud_health_check_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        return False, error_msg


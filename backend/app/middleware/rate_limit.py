"""
API Global Rate Limit Middleware

Provides fast, unified protection for all API endpoints without accessing the database.
Uses memory cache for best performance.
"""

import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from utils.logging import get_logger

logger = get_logger(__name__)


class APIRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Global API rate limit middleware.

    Protects all /api/v1/* endpoints with IP-based rate limiting.
    Does not access database for performance.

    Configuration is loaded on application startup from system_configs
    and stored in app.state:
    - app.state.api_rate_limit_requests: Max requests per window (default: 100)
    - app.state.api_rate_limit_window_seconds: Time window in seconds (default: 60)
    """

    def __init__(self, app):
        """
        Initialize middleware.

        Args:
            app: FastAPI application
        """
        super().__init__(app)
        self._cache: dict[str, deque] = {}

        logger.info("api_rate_limit_middleware_initialized")

    async def dispatch(self, request: Request, call_next):
        """
        Process request with rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response or rate limit error
        """
        # Only apply to API endpoints
        if not request.url.path.startswith("/api/v1/"):
            return await call_next(request)

        # Get configuration from app state (loaded on startup)
        requests = getattr(request.app.state, "api_rate_limit_requests", 100)
        window_seconds = getattr(request.app.state, "api_rate_limit_window_seconds", 60)

        ip = request.client.host

        # Check rate limit
        now = time.time()

        # Initialize cache for this IP if not exists
        if ip not in self._cache:
            self._cache[ip] = deque()

        # Remove old requests outside the window
        while self._cache[ip] and self._cache[ip][0] < now - window_seconds:
            self._cache[ip].popleft()

        # Check if limit exceeded
        if len(self._cache[ip]) >= requests:
            # Calculate retry_after
            oldest_request = self._cache[ip][0]
            retry_after = int(window_seconds - (now - oldest_request)) + 1

            logger.warning(
                "api_rate_limit_exceeded",
                ip=ip,
                path=request.url.path,
                requests_count=len(self._cache[ip]),
                retry_after=retry_after,
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "请求过于频繁，请稍后再试",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        # Record this request
        self._cache[ip].append(now)

        # Clean up old IPs periodically (every 1000 requests)
        if len(self._cache) > 1000:
            self._cleanup_cache(now, window_seconds)

        return await call_next(request)

    def _cleanup_cache(self, now: float, window_seconds: int) -> None:
        """
        Clean up cache entries for IPs with no recent requests.

        Args:
            now: Current timestamp
            window_seconds: Time window in seconds
        """
        ips_to_remove = []

        for ip, requests in self._cache.items():
            # Remove old requests
            while requests and requests[0] < now - window_seconds:
                requests.popleft()

            # Mark IP for removal if no recent requests
            if not requests:
                ips_to_remove.append(ip)

        # Remove marked IPs
        for ip in ips_to_remove:
            del self._cache[ip]

        if ips_to_remove:
            logger.info(
                "api_rate_limit_cache_cleaned",
                removed_ips_count=len(ips_to_remove),
                remaining_ips_count=len(self._cache),
            )

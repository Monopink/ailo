"""API global rate limit middleware providing fast, in-memory protection."""

import time
from collections import deque
from collections.abc import Awaitable, Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.exceptions.error_codes import build_error_code
from app.utils.client_ip import ClientIPResolutionError, get_client_ip
from app.utils.logging import get_logger

logger = get_logger(__name__)

MAX_RATE_LIMIT_CACHE_SIZE = 1000
REQUEST_ID_HEADER = "X-Request-ID"


class APIRateLimitMiddleware(BaseHTTPMiddleware):
    """Global API rate limit middleware.

    Protects all /api/v1/* endpoints with IP-based rate limiting.
    Does not access database for performance.

    Configuration is loaded on application startup from system_configs
    and stored in app.state:
    - app.state.api_rate_limit_requests: Max requests per window (default: 100)
    - app.state.api_rate_limit_window_seconds: Time window in seconds (default: 60)
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize middleware.

        Args:
            app: FastAPI application

        """
        super().__init__(app)
        self._cache: dict[str, deque[float]] = {}

        logger.info("api_rate_limit_middleware_initialized")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request with rate limiting.

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
        requests = getattr(request.app.state, "api_rate_limit_requests", None)
        window_seconds = getattr(request.app.state, "api_rate_limit_window_seconds", None)
        if not isinstance(requests, int) or not isinstance(window_seconds, int):
            logger.critical(
                "api_rate_limit_config_missing",
                has_requests=isinstance(requests, int),
                has_window_seconds=isinstance(window_seconds, int),
            )
            request_id = self._get_or_create_request_id(request)
            message = "系统错误"
            error_code = build_error_code(path=request.url.path, status_code=500, detail=message)
            return JSONResponse(
                status_code=500,
                content={
                    "error_code": error_code,
                    "message": message,
                    "request_id": request_id,
                },
                headers={REQUEST_ID_HEADER: request_id},
            )

        try:
            ip = get_client_ip(request)
        except ClientIPResolutionError as exc:
            logger.warning(
                "api_rate_limit_client_ip_invalid",
                reason=exc.reason,
                detail=str(exc),
                path=request.url.path,
            )
            request_id = self._get_or_create_request_id(request)
            message = "请求来源无效"
            error_code = build_error_code(path=request.url.path, status_code=400, detail=message)
            return JSONResponse(
                status_code=400,
                content={
                    "error_code": error_code,
                    "message": message,
                    "request_id": request_id,
                },
                headers={REQUEST_ID_HEADER: request_id},
            )

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

            request_id = self._get_or_create_request_id(request)
            message = "请求过于频繁，请稍后再试"
            error_code = build_error_code(path=request.url.path, status_code=429, detail=message)

            return JSONResponse(
                status_code=429,
                content={
                    "error_code": error_code,
                    "message": message,
                    "request_id": request_id,
                },
                headers={"Retry-After": str(retry_after), REQUEST_ID_HEADER: request_id},
            )

        # Record this request
        self._cache[ip].append(now)

        # Clean up old IPs periodically (every 1000 requests)
        if len(self._cache) > MAX_RATE_LIMIT_CACHE_SIZE:
            self._cleanup_cache(now, window_seconds)

        return await call_next(request)

    def _cleanup_cache(self, now: float, window_seconds: int) -> None:
        """Clean up cache entries for IPs with no recent requests.

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

    @staticmethod
    def _get_or_create_request_id(request: Request) -> str:
        request_id = getattr(request.state, "request_id", None)
        if isinstance(request_id, str) and request_id:
            return request_id

        header_value = request.headers.get(REQUEST_ID_HEADER) or request.headers.get(
            REQUEST_ID_HEADER.lower()
        )
        if header_value:
            request_id = header_value
        else:
            request_id = f"req_{uuid4().hex[:12]}"

        request.state.request_id = request_id
        return request_id

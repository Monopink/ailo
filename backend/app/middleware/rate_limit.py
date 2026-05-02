"""API global rate limit middleware providing fast, in-memory protection."""

import time
from collections import deque
from collections.abc import Awaitable, Callable
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.database import get_sessionmaker
from app.enums import DetectionSource
from app.exceptions.error_codes import build_error_code
from app.models.user import User, UserToken
from app.services.security import SecurityRequestContext, enforce_attack_scan, is_ip_blocked
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

    async def dispatch(  # noqa: PLR0911
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
            # Configuration might not be available in certain environments (e.g. tests).
            # In that case, skip rate limiting rather than failing requests.
            logger.warning(
                "api_rate_limit_config_missing_skip",
                has_requests=isinstance(requests, int),
                has_window_seconds=isinstance(window_seconds, int),
            )
            return await call_next(request)

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

        request_id = self._get_or_create_request_id(request)
        session_factory = get_sessionmaker()
        async with session_factory() as db:
            if await is_ip_blocked(db, ip):
                return self._build_denied_response(
                    path=request.url.path,
                    request_id=request_id,
                    reason="IP_BLOCKED",
                )

            user = await self._resolve_user_from_bearer_token(request=request, db=db)
            match = await enforce_attack_scan(
                db,
                context=SecurityRequestContext(
                    detection_source=DetectionSource.MIDDLEWARE,
                    request_method=request.method,
                    request_path=request.url.path,
                    client_ip=ip,
                    request_id=request_id,
                    user_id=int(user.id) if user is not None else None,
                    user_qiao_id=str(user.qiao_id) if user is not None else None,
                ),
                fields={
                    "path": request.url.path,
                    "query": request.url.query or "",
                    "user_agent": request.headers.get("User-Agent", ""),
                },
                extra_evidence={"layer": "api_rate_limit_middleware"},
            )
            if match is not None:
                logger.warning(
                    "api_attack_blocked_by_middleware",
                    rule_code=match.rule_code,
                    path=request.url.path,
                    method=request.method,
                    ip=ip,
                    request_id=request_id,
                )
                return self._build_denied_response(
                    path=request.url.path,
                    request_id=request_id,
                    reason="ATTACK_DETECTED",
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

    @staticmethod
    async def _resolve_user_from_bearer_token(request: Request, db: AsyncSession) -> User | None:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:].strip()
        if token == "":
            return None

        token_result = await db.execute(
            select(UserToken).where(
                and_(
                    UserToken.access_token == token,
                    UserToken.status == 1,
                    UserToken.access_revoked_at.is_(None),
                )
            )
        )
        user_token = token_result.scalar_one_or_none()
        if user_token is None:
            return None

        user_result = await db.execute(select(User).where(User.id == user_token.user_id))
        return user_result.scalar_one_or_none()

    @staticmethod
    def _build_denied_response(*, path: str, request_id: str, reason: str) -> JSONResponse:
        message = "请求来源受限"
        error_code = build_error_code(path=path, status_code=403, detail=message)
        return JSONResponse(
            status_code=403,
            content={
                "error_code": error_code,
                "message": message,
                "reason": reason,
                "request_id": request_id,
            },
            headers={REQUEST_ID_HEADER: request_id},
        )

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

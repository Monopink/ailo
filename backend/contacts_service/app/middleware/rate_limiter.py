"""
Rate limiting middleware for contacts service API endpoints
Prevents abuse and excessive API calls
"""

import time
from typing import Dict, List, Tuple
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from ..utils.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    In-memory rate limiter for API endpoints
    Tracks requests per user and endpoint
    """

    def __init__(self):
        # Store request history: {user_id: {endpoint: [(timestamp, count), ...]}}
        self.request_history: Dict[str, Dict[str, List[Tuple[float, int]]]] = {}
        # Rate limit rules: {endpoint_pattern: (max_requests, time_window_seconds)}
        self.rate_limits = {
            "/api/v1/contacts/search": (5, 60),  # 5 requests per minute
            "/api/v1/contacts/add": (3, 60),  # 3 requests per minute
        }
        # Track last cleanup time to prevent excessive cleanup calls
        self.last_cleanup_time = time.time()

    def is_allowed(self, user_id: str, endpoint: str) -> Tuple[bool, str]:
        """
        Check if request is allowed based on rate limits

        Args:
            user_id: User identifier
            endpoint: API endpoint path

        Returns:
            Tuple of (is_allowed, error_message)
        """
        # Find matching rate limit rule
        rate_limit_rule = None
        for pattern, rule in self.rate_limits.items():
            if endpoint.startswith(pattern):
                rate_limit_rule = rule
                break

        if not rate_limit_rule:
            # No rate limit for this endpoint
            return True, ""

        max_requests, time_window = rate_limit_rule
        current_time = time.time()

        # Initialize user history if not exists
        if user_id not in self.request_history:
            self.request_history[user_id] = {}

        if endpoint not in self.request_history[user_id]:
            self.request_history[user_id][endpoint] = []

        # Clean old entries outside time window
        history = self.request_history[user_id][endpoint]
        cutoff_time = current_time - time_window
        self.request_history[user_id][endpoint] = [
            (timestamp, count) for timestamp, count in history if timestamp > cutoff_time
        ]

        # Count total requests in time window
        total_requests = sum(count for _, count in self.request_history[user_id][endpoint])

        if total_requests >= max_requests:
            logger.warning(
                "rate_limit_exceeded",
                user_id=user_id,
                endpoint=endpoint,
                total_requests=total_requests,
                max_requests=max_requests,
                time_window=time_window,
            )
            return False, f"Rate limit exceeded. Maximum {max_requests} requests per {time_window} seconds."

        # Record this request
        self.request_history[user_id][endpoint].append((current_time, 1))

        # Cleanup old users to prevent memory leak (every 5 minutes)
        if current_time - self.last_cleanup_time > 300:  # 5 minutes
            self._cleanup_old_entries(current_time)
            self.last_cleanup_time = current_time

        return True, ""

    def _cleanup_old_entries(self, current_time: float):
        """Clean up old entries to prevent memory leak"""
        cutoff_time = current_time - 3600  # 1 hour
        users_to_remove = []

        logger.debug("rate_limiter_cleanup_started", total_users=len(self.request_history))

        for user_id, endpoints in self.request_history.items():
            endpoints_to_remove = []
            for endpoint, history in endpoints.items():
                # Remove old entries
                new_history = [(t, c) for t, c in history if t > cutoff_time]
                if new_history:
                    endpoints[endpoint] = new_history
                else:
                    endpoints_to_remove.append(endpoint)

            # Remove empty endpoints
            for endpoint in endpoints_to_remove:
                del endpoints[endpoint]

            # Mark user for removal if no endpoints left
            if not endpoints:
                users_to_remove.append(user_id)

        # Remove empty users
        for user_id in users_to_remove:
            del self.request_history[user_id]

        logger.debug(
            "rate_limiter_cleanup_completed",
            users_removed=len(users_to_remove),
            remaining_users=len(self.request_history),
        )


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting
    """

    async def dispatch(self, request: Request, call_next):
        """
        Process request and apply rate limiting
        """
        # Skip rate limiting for non-protected endpoints
        if not self._should_rate_limit(request.url.path):
            return await call_next(request)

        # Extract user ID from request
        user_id = self._extract_user_id(request)
        if not user_id:
            # No user ID found, skip rate limiting
            return await call_next(request)

        # Check rate limit
        is_allowed, error_message = rate_limiter.is_allowed(user_id, request.url.path)

        if not is_allowed:
            logger.warning(
                "request_rate_limited",
                user_id=user_id,
                endpoint=request.url.path,
                method=request.method,
                client_ip=request.client.host if request.client else "unknown",
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error_code": 1002,
                    "message": "请求过于频繁，请稍后再试",
                    "details": error_message,
                },
            )

        # Process request normally
        response = await call_next(request)
        return response

    def _should_rate_limit(self, path: str) -> bool:
        """Check if path should be rate limited"""
        protected_paths = ["/api/v1/contacts/search", "/api/v1/contacts/add"]
        return any(path.startswith(protected_path) for protected_path in protected_paths)

    def _extract_user_id(self, request: Request) -> str:
        """Extract user ID from request for rate limiting"""
        # Try to get user from JWT token in Authorization header
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                # Import here to avoid circular imports
                from ..core.auth import decode_token

                token = auth_header.split(" ")[1]
                payload = decode_token(token)
                if payload and "entity_id" in payload:
                    return str(payload["entity_id"])
            except Exception as e:
                logger.debug("failed_to_extract_user_from_token", error=str(e))

        # Fallback to IP address if no user ID available
        if request.client:
            return f"ip_{request.client.host}"

        return "unknown"

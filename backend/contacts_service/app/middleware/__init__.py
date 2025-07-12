"""
Middleware package for contacts service
"""

from .rate_limiter import RateLimitMiddleware

__all__ = ["RateLimitMiddleware"]

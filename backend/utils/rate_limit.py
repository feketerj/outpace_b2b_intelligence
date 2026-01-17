"""
Rate limiting middleware for API protection.

Prevents abuse by limiting requests per IP address.
Different limits for different endpoint categories.
"""

import os
import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Rate limit configuration (can be overridden via env vars)
DEFAULT_RATE_LIMIT = os.environ.get("RATE_LIMIT_DEFAULT", "100/minute")
AUTH_RATE_LIMIT = os.environ.get("RATE_LIMIT_AUTH", "10/minute")
UPLOAD_RATE_LIMIT = os.environ.get("RATE_LIMIT_UPLOAD", "20/minute")

# Create the limiter with IP-based key
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[DEFAULT_RATE_LIMIT],
    storage_uri=os.environ.get("RATE_LIMIT_STORAGE", "memory://"),  # Use Redis in production
    strategy="fixed-window",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.

    Returns a JSON response with clear error message and retry-after header.
    """
    logger.warning(
        f"[audit.rate_limit_exceeded] ip={get_remote_address(request)} "
        f"path={request.url.path} limit={exc.detail}"
    )

    # Extract retry-after from the exception if available
    retry_after = getattr(exc, "retry_after", 60)

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Too many requests.",
            "retry_after_seconds": retry_after,
        },
        headers={"Retry-After": str(retry_after)}
    )


# Decorators for different rate limits
def auth_rate_limit():
    """Stricter rate limit for authentication endpoints (login, register, password reset)."""
    return limiter.limit(AUTH_RATE_LIMIT)


def upload_rate_limit():
    """Rate limit for file upload endpoints."""
    return limiter.limit(UPLOAD_RATE_LIMIT)


def default_rate_limit():
    """Standard rate limit for most endpoints."""
    return limiter.limit(DEFAULT_RATE_LIMIT)


def no_rate_limit():
    """Exempt from rate limiting (for health checks, etc.)."""
    return limiter.exempt

"""
Rate Limiting Configuration - Container-Aware (FIX P4)

This module provides container-aware rate limiting functions that properly
extract client IPs from proxy headers (X-Forwarded-For, X-Real-IP, etc.)
instead of using the container/ingress IP.

Usage:
    from rate_limiting import get_user_id_or_ip, limiter

    # Configure limiter on app
    app.state.limiter = limiter

    # Use in endpoints
    @app.get("/api/example")
    @limiter.limit("100/minute")
    async def example_endpoint(request: Request):
        ...
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_real_client_ip(request: Request) -> str:
    """
    Extract real client IP from proxy headers.
    Supports: X-Forwarded-For, X-Real-IP, CF-Connecting-IP (Cloudflare)

    In containerized environments (Docker/K8s), all requests appear from
    the ingress IP. This function extracts the true client IP.

    Priority:
    1. CF-Connecting-IP (Cloudflare)
    2. X-Forwarded-For (first IP in chain)
    3. X-Real-IP (Nginx)
    4. Direct connection IP (fallback)
    """
    # Cloudflare
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip

    # Standard proxy header (most common)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in chain is original client
        return forwarded.split(",")[0].strip()

    # Nginx real IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct connection
    return get_remote_address(request)


def get_user_id_or_ip(request: Request) -> str:
    """
    Prefer user ID for authenticated requests, fall back to IP.

    This ensures rate limiting is per-user for authenticated requests,
    preventing a single user from exhausting the rate limit for everyone.

    The X-User-ID header should be set by the Flask backend after
    authenticating the user.

    Returns:
        "user:{user_id}" for authenticated requests
        "ip:{client_ip}" for unauthenticated requests
    """
    # Check for user ID in header (set by Flask after auth)
    user_id = request.headers.get("X-User-ID")
    if user_id:
        return f"user:{user_id}"

    return f"ip:{get_real_client_ip(request)}"


# Initialize rate limiter with user-aware key function
# Default: 200 requests per minute per user/IP
limiter = Limiter(key_func=get_user_id_or_ip, default_limits=["200/minute"])

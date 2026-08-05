"""Rate limiting configuration for ApplyPilot API.

Uses slowapi with in-memory storage for single-instance deployment.
Limits are generous for personal use but prevent abuse.
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request


def _key_func(request: Request) -> str:
    """Key function: use remote IP for rate limiting."""
    return get_remote_address(request)


# Create the limiter instance
limiter = Limiter(key_func=_key_func)

# Default rate limits per endpoint category
RATE_LIMITS = {
    "default": "60/minute",         # General API endpoints
    "agent_trigger": "5/minute",    # Agent trigger (expensive operation)
    "settings_write": "20/minute",  # Settings mutations
    "upload": "10/minute",          # File uploads
    "test_connection": "5/minute",  # External connection tests
    "auth": "10/minute",            # Auth-related (login attempts)
    "export": "3/minute",           # Data exports (expensive)
}

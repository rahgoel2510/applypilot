"""
API key authentication middleware for ApplyPilot's FastAPI backend.

Reads the API key from the APPLYPILOT_API_KEY environment variable.
If no key is configured, generates a random one and prints it to the console
so the user can add it to their .env file.

Exports:
    API_KEY: The active API key string (for use in generating WebSocket URLs, etc.)
    api_key_middleware: Async middleware function for FastAPI/Starlette.
"""

import os
import secrets
from typing import Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# ---------------------------------------------------------------------------
# API Key Initialization
# ---------------------------------------------------------------------------

_env_key = os.environ.get("APPLYPILOT_API_KEY", "").strip()

if _env_key:
    API_KEY: str = _env_key
else:
    API_KEY = secrets.token_urlsafe(32)
    print(
        "\n"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║  No APPLYPILOT_API_KEY found in environment.               ║\n"
        "║  Generated a temporary key for this session:               ║\n"
        f"║  {API_KEY:<56} ║\n"
        "║                                                            ║\n"
        "║  Add this to your .env file to persist it:                 ║\n"
        f"║  APPLYPILOT_API_KEY={API_KEY:<37} ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n"
    )

# ---------------------------------------------------------------------------
# Paths that do not require authentication
# ---------------------------------------------------------------------------

_PUBLIC_PATHS: set[str] = {
    "/api/stats",
    "/api/health",
    "/docs",
    "/openapi.json",
    "/",
    "/favicon.ico",
    "/metrics",
}


def _is_public_path(path: str) -> bool:
    """Return True if the path is exempt from authentication."""
    if path in _PUBLIC_PATHS:
        return True
    if path.startswith("/assets"):
        return True
    return False


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


async def api_key_middleware(
    request: Request, call_next: Callable[[Request], Response]
) -> Response:
    """
    Authenticate incoming requests using an API key.

    - Public paths are exempt (health, docs, static assets, etc.).
    - WebSocket paths check the ``token`` query parameter.
    - All other paths check the ``X-API-Key`` header or
      ``Authorization: Bearer <token>`` header.

    Returns a 401 JSON response on failure.
    """
    path: str = request.url.path

    # Allow public/exempt paths through without auth
    if _is_public_path(path):
        return await call_next(request)

    # WebSocket authentication via query parameter
    if path.startswith("/ws"):
        token = request.query_params.get("token", "")
        if secrets.compare_digest(token, API_KEY):
            return await call_next(request)
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized - provide X-API-Key header"},
        )

    # Standard HTTP authentication via header
    api_key_header = request.headers.get("X-API-Key", "")
    auth_header = request.headers.get("Authorization", "")

    # Check X-API-Key header
    if api_key_header and secrets.compare_digest(api_key_header, API_KEY):
        return await call_next(request)

    # Check Authorization: Bearer <token>
    if auth_header.startswith("Bearer "):
        bearer_token = auth_header[7:]  # len("Bearer ") == 7
        if secrets.compare_digest(bearer_token, API_KEY):
            return await call_next(request)

    return JSONResponse(
        status_code=401,
        content={"detail": "Unauthorized - provide X-API-Key header"},
    )

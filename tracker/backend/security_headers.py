"""Security headers middleware for hardening HTTP responses."""

from fastapi import Request
from starlette.responses import Response


async def security_headers_middleware(request: Request, call_next) -> Response:
    """Add security headers to every response.

    Headers applied:
        - X-Content-Type-Options: nosniff
        - X-Frame-Options: DENY
        - X-XSS-Protection: 1; mode=block
        - Strict-Transport-Security: max-age=31536000; includeSubDomains
        - Referrer-Policy: strict-origin-when-cross-origin
        - Permissions-Policy: camera=(), microphone=(), geolocation=()
        - Content-Security-Policy: restrictive default policy
        - Cache-Control: no-store (for /api paths only)
    """
    response: Response = await call_next(request)

    # Core security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' ws: wss:"
    )

    # Cache-Control: no-store for API responses
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"

    return response

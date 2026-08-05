"""Request tracing middleware — propagates correlation IDs across the request lifecycle.

Generates or reads X-Request-ID on incoming requests and makes it available
via get_request_id() throughout the request lifecycle.
"""

import uuid
from contextvars import ContextVar
from starlette.requests import Request
from starlette.responses import Response

_request_id: ContextVar[str] = ContextVar('request_id', default='')

REQUEST_ID_HEADER = 'X-Request-ID'


def get_request_id() -> str:
    """Get the current request's correlation ID. Returns empty string if not in request context."""
    return _request_id.get('')


async def request_tracing_middleware(request: Request, call_next) -> Response:
    """Middleware that sets a correlation ID for the request lifecycle.
    
    - Reads X-Request-ID from incoming headers (from upstream proxy/gateway)
    - If not present, generates a new UUID
    - Stores in ContextVar for downstream access
    - Adds X-Request-ID to response headers
    """
    # Read or generate request ID
    request_id = request.headers.get(REQUEST_ID_HEADER, '') or uuid.uuid4().hex[:16]
    
    # Set in context var
    token = _request_id.set(request_id)
    
    try:
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    finally:
        _request_id.reset(token)

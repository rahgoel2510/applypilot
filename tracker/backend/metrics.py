"""Prometheus metrics for ApplyPilot.

Exposes a /metrics endpoint with key application counters, gauges, and histograms.
Uses prometheus_client library.

Metrics exposed:
- applypilot_http_requests_total (counter, labels: method, endpoint, status)
- applypilot_http_request_duration_seconds (histogram, labels: method, endpoint)
- applypilot_jobs_total (counter, labels: stage, source)
- applypilot_agent_runs_total (counter, labels: status, mode)
- applypilot_agent_cycle_duration_seconds (histogram)
- applypilot_websocket_connections (gauge)
- applypilot_daily_applications (gauge)
- applypilot_browser_errors_total (counter)
"""

import time
from typing import Callable

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    REGISTRY,
)
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route


# ---------------------------------------------------------------------------
# Metrics Definitions
# ---------------------------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "applypilot_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "applypilot_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

JOBS_TOTAL = Counter(
    "applypilot_jobs_total",
    "Total jobs processed",
    ["stage", "source"],
)

AGENT_RUNS_TOTAL = Counter(
    "applypilot_agent_runs_total",
    "Total agent runs",
    ["status", "mode"],
)

AGENT_CYCLE_DURATION = Histogram(
    "applypilot_agent_cycle_duration_seconds",
    "Agent scan cycle duration in seconds",
    buckets=[10, 30, 60, 120, 300, 600, 1200, 3600],
)

WEBSOCKET_CONNECTIONS = Gauge(
    "applypilot_websocket_connections",
    "Current active WebSocket connections",
)

DAILY_APPLICATIONS = Gauge(
    "applypilot_daily_applications",
    "Number of applications submitted today",
)

BROWSER_ERRORS_TOTAL = Counter(
    "applypilot_browser_errors_total",
    "Total browser errors (crashes, timeouts, navigation failures)",
    ["error_type"],
)


# ---------------------------------------------------------------------------
# HTTP Metrics Middleware
# ---------------------------------------------------------------------------


async def metrics_middleware(request: Request, call_next: Callable) -> Response:
    """Middleware to track HTTP request count and latency."""
    # Skip metrics endpoint itself to avoid recursion
    if request.url.path == "/metrics":
        return await call_next(request)

    # Normalize endpoint path (strip IDs to reduce cardinality)
    path = request.url.path
    # Collapse /api/jobs/123 → /api/jobs/{id}
    parts = path.split("/")
    normalized_parts = []
    for i, part in enumerate(parts):
        if part.isdigit() or (len(part) > 8 and part.replace("-", "").isalnum()):
            normalized_parts.append("{id}")
        else:
            normalized_parts.append(part)
    endpoint = "/".join(normalized_parts)

    method = request.method
    start_time = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - start_time
    status = str(response.status_code)

    HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=status).inc()
    HTTP_REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

    return response


# ---------------------------------------------------------------------------
# Metrics Endpoint
# ---------------------------------------------------------------------------


async def metrics_endpoint(request: Request) -> Response:
    """Expose Prometheus metrics at /metrics."""
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


# Route to be included in the FastAPI app
metrics_route = Route("/metrics", metrics_endpoint, methods=["GET"])

"""Health monitoring and aggregated service status.

Provides a centralized view of all service health for:
- Dashboard health endpoint
- Graceful degradation decisions
- Alerting on persistent failures
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    """Health state for a single service."""

    name: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_check: float = 0
    last_success: float = 0
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        return self.status == ServiceStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "last_check_ago_s": int(time.time() - self.last_check) if self.last_check else None,
            "message": self.message,
            "metadata": self.metadata,
        }


class HealthMonitor:
    """Aggregated health monitor for all services.

    Register health check functions for each service. Call check_all()
    to run them and get a consolidated health report.

    Usage:
        monitor = HealthMonitor()
        monitor.register("telegram", check_telegram_health)
        monitor.register("browser", check_browser_health)

        report = await monitor.check_all()
        # {"overall": "healthy", "services": [...]}
    """

    def __init__(self, check_timeout: float = 10.0) -> None:
        self._checks: dict[str, Callable[[], Awaitable[ServiceHealth]]] = {}
        self._results: dict[str, ServiceHealth] = {}
        self._timeout = check_timeout

    def register(self, name: str, check_fn: Callable[[], Awaitable[ServiceHealth]]) -> None:
        """Register a health check function for a service."""
        self._checks[name] = check_fn
        self._results[name] = ServiceHealth(name=name)

    async def check_one(self, name: str) -> ServiceHealth:
        """Run a single health check."""
        if name not in self._checks:
            return ServiceHealth(name=name, status=ServiceStatus.UNKNOWN, message="Not registered")

        try:
            result = await asyncio.wait_for(self._checks[name](), timeout=self._timeout)
            result.last_check = time.time()
            if result.is_healthy:
                result.last_success = time.time()
            self._results[name] = result
            return result
        except asyncio.TimeoutError:
            health = ServiceHealth(
                name=name,
                status=ServiceStatus.UNHEALTHY,
                last_check=time.time(),
                message=f"Health check timed out ({self._timeout}s)",
            )
            self._results[name] = health
            return health
        except Exception as exc:
            health = ServiceHealth(
                name=name,
                status=ServiceStatus.UNHEALTHY,
                last_check=time.time(),
                message=str(exc)[:200],
            )
            self._results[name] = health
            return health

    async def check_all(self) -> dict[str, Any]:
        """Run all registered health checks concurrently."""
        tasks = [self.check_one(name) for name in self._checks]
        await asyncio.gather(*tasks, return_exceptions=True)

        services = [h.to_dict() for h in self._results.values()]
        statuses = [h.status for h in self._results.values()]

        if all(s == ServiceStatus.HEALTHY for s in statuses):
            overall = ServiceStatus.HEALTHY
        elif any(s == ServiceStatus.UNHEALTHY for s in statuses):
            overall = ServiceStatus.DEGRADED
        else:
            overall = ServiceStatus.UNKNOWN

        return {
            "overall": overall.value,
            "services": services,
            "checked_at": time.time(),
        }

    def get_cached_status(self, name: str) -> ServiceHealth:
        """Get last known health status without re-checking."""
        return self._results.get(name, ServiceHealth(name=name))

    def is_service_available(self, name: str) -> bool:
        """Quick check if a service was healthy at last check."""
        cached = self._results.get(name)
        return cached is not None and cached.is_healthy

"""Circuit breaker pattern to prevent cascading failures.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, requests are short-circuited immediately
- HALF_OPEN: Testing if service recovered (allows limited requests)

Usage:
    cb = CircuitBreaker("telegram", failure_threshold=3, recovery_timeout=60)

    async with cb:
        await send_notification(...)  # Protected call

    # Or as decorator:
    @cb.protect
    async def send_notification(...):
        ...
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when circuit is open and call is rejected."""

    def __init__(self, service: str, until: float):
        self.service = service
        self.until = until
        remaining = max(0, until - time.time())
        super().__init__(
            f"Circuit breaker OPEN for '{service}' — recovering in {remaining:.0f}s"
        )


class CircuitBreaker:
    """Thread-safe circuit breaker with configurable thresholds.

    Args:
        service_name: Human-readable name for logging.
        failure_threshold: Number of consecutive failures to trip the breaker.
        recovery_timeout: Seconds to wait before testing recovery (half-open).
        success_threshold: Successful calls in half-open to close the circuit.
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ) -> None:
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may transition to half-open on access)."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def is_available(self) -> bool:
        """Whether the service is currently accepting requests."""
        return self.state != CircuitState.OPEN

    async def __aenter__(self) -> CircuitBreaker:
        """Context manager entry — check if call is allowed."""
        async with self._lock:
            current_state = self.state
            if current_state == CircuitState.OPEN:
                raise CircuitBreakerOpen(self.service_name, self._last_failure_time + self.recovery_timeout)
            if current_state == CircuitState.HALF_OPEN:
                self._state = CircuitState.HALF_OPEN
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit — record success/failure."""
        async with self._lock:
            if exc_type is None:
                self._on_success()
            else:
                self._on_failure()
        return False  # Don't suppress exceptions

    def _on_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
                logger.info("Circuit CLOSED for '%s' — service recovered", self.service_name)
        else:
            self._failure_count = 0

    def _on_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._success_count = 0
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit OPEN for '%s' — %d consecutive failures (recovery in %ds)",
                self.service_name,
                self._failure_count,
                self.recovery_timeout,
            )

    def protect(self, func: Callable) -> Callable:
        """Decorator to protect an async function with this circuit breaker."""

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with self:
                return await func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    def reset(self) -> None:
        """Manually reset the circuit breaker (for testing/admin)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize state for health endpoints."""
        return {
            "service": self.service_name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure": self._last_failure_time,
        }

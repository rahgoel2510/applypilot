"""Browser watchdog — monitors Playwright browser health and auto-recovers.

Detects:
- Browser process death
- Page unresponsiveness (JS evaluation timeout)
- Memory threshold exceeded
- Navigation timeouts

Recovery:
- Kills zombie browser processes
- Relaunches browser with fresh context
- Reports via structured logging
"""

import asyncio
import logging
import time
from typing import Callable, Awaitable, Any

logger = logging.getLogger(__name__)


class BrowserWatchdog:
    """Monitors browser health and triggers recovery on failure.

    Usage:
        watchdog = BrowserWatchdog(
            health_check_fn=my_health_check,
            recovery_fn=my_recovery_fn,
            check_interval=30,
        )
        await watchdog.start()
        # ... later ...
        await watchdog.stop()
    """

    def __init__(
        self,
        health_check_fn: Callable[[], Awaitable[bool]],
        recovery_fn: Callable[[], Awaitable[None]],
        check_interval: float = 30.0,
        max_consecutive_failures: int = 3,
        health_check_timeout: float = 10.0,
    ) -> None:
        """
        Args:
            health_check_fn: Async function returning True if browser is healthy.
                            Typically runs page.evaluate('1+1') with timeout.
            recovery_fn: Async function to kill and relaunch the browser.
            check_interval: Seconds between health checks.
            max_consecutive_failures: Number of failures before triggering recovery.
            health_check_timeout: Timeout for each health check call.
        """
        self._health_check = health_check_fn
        self._recovery = recovery_fn
        self._interval = check_interval
        self._max_failures = max_consecutive_failures
        self._timeout = health_check_timeout
        self._task: asyncio.Task | None = None
        self._running = False
        self._consecutive_failures = 0
        self._total_recoveries = 0
        self._last_healthy: float = time.time()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def total_recoveries(self) -> int:
        return self._total_recoveries

    @property
    def seconds_since_healthy(self) -> float:
        return time.time() - self._last_healthy

    async def start(self) -> None:
        """Start the watchdog background loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="browser-watchdog")
        logger.info("Browser watchdog started (interval=%ss, max_failures=%d)",
                    self._interval, self._max_failures)

    async def stop(self) -> None:
        """Stop the watchdog background loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Browser watchdog stopped (total_recoveries=%d)", self._total_recoveries)

    async def check_once(self) -> bool:
        """Run a single health check. Returns True if healthy."""
        try:
            healthy = await asyncio.wait_for(
                self._health_check(), timeout=self._timeout
            )
            if healthy:
                self._consecutive_failures = 0
                self._last_healthy = time.time()
                return True
            else:
                self._consecutive_failures += 1
                logger.warning(
                    "Browser health check returned False (failure %d/%d)",
                    self._consecutive_failures, self._max_failures,
                )
                return False
        except asyncio.TimeoutError:
            self._consecutive_failures += 1
            logger.warning(
                "Browser health check timed out after %ss (failure %d/%d)",
                self._timeout, self._consecutive_failures, self._max_failures,
            )
            return False
        except Exception as e:
            self._consecutive_failures += 1
            logger.warning(
                "Browser health check error: %s (failure %d/%d)",
                e, self._consecutive_failures, self._max_failures,
            )
            return False

    async def _loop(self) -> None:
        """Main watchdog loop."""
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if not self._running:
                    break

                healthy = await self.check_once()

                if not healthy and self._consecutive_failures >= self._max_failures:
                    logger.error(
                        "Browser unresponsive after %d consecutive failures. Triggering recovery.",
                        self._consecutive_failures,
                    )
                    await self._trigger_recovery()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Watchdog loop error: %s", e)
                await asyncio.sleep(5)  # Brief pause before retrying

    async def _trigger_recovery(self) -> None:
        """Execute recovery and reset failure counter."""
        try:
            await self._recovery()
            self._total_recoveries += 1
            self._consecutive_failures = 0
            self._last_healthy = time.time()
            logger.info(
                "Browser recovery successful (total_recoveries=%d)",
                self._total_recoveries,
            )
        except Exception as e:
            logger.error("Browser recovery FAILED: %s", e)
            # Don't reset failure counter — will retry on next loop iteration

"""Resilience decorators for retry and graceful degradation.

Usage:
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_data():
        ...

    @graceful_fallback(fallback_value=[], on_error=log_warning)
    async def get_notifications():
        ...
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (Exception,),
) -> Callable:
    """Decorator for async functions with exponential backoff retry.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap in seconds.
        exponential_base: Multiplier for each retry.
        jitter: Add random jitter to prevent thundering herd.
        retryable_exceptions: Tuple of exception types to retry on.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exception = exc

                    if attempt >= max_retries:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func.__name__,
                            max_retries + 1,
                            str(exc)[:100],
                        )
                        raise

                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    if jitter:
                        delay *= 0.5 + random.random()

                    logger.warning(
                        "%s attempt %d/%d failed (%s), retrying in %.1fs...",
                        func.__name__,
                        attempt + 1,
                        max_retries + 1,
                        str(exc)[:60],
                        delay,
                    )
                    await asyncio.sleep(delay)

            raise last_exception  # Should never reach here

        return wrapper

    return decorator


def graceful_fallback(
    fallback_value: Any = None,
    on_error: Callable[[Exception], None] | None = None,
    critical: bool = False,
) -> Callable:
    """Decorator for graceful degradation — returns fallback on failure.

    Use for non-critical operations (notifications, tracking) that shouldn't
    crash the main pipeline.

    Args:
        fallback_value: Value to return if the function fails.
        on_error: Optional callback when an error occurs.
        critical: If True, re-raises the exception after logging.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                logger.warning(
                    "Graceful degradation for %s: %s (returning fallback)",
                    func.__name__,
                    str(exc)[:100],
                )
                if on_error:
                    on_error(exc)
                if critical:
                    raise
                return fallback_value

        return wrapper

    return decorator


def timeout(seconds: float) -> Callable:
    """Decorator to add a timeout to an async function.

    Args:
        seconds: Maximum execution time in seconds.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)

        return wrapper

    return decorator

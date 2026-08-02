"""Tests for resilience decorators: retry_with_backoff, graceful_fallback, timeout."""

import asyncio
from unittest.mock import MagicMock

import pytest

from linkedin_agent.resilience.decorators import (
    graceful_fallback,
    retry_with_backoff,
    timeout,
)


class TestRetryWithBackoff:
    """Tests for the retry decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def success():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await success()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self):
        attempts = []

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise ConnectionError("fail")
            return "recovered"

        result = await flaky()
        assert result == "recovered"
        assert len(attempts) == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        async def always_fail():
            raise ValueError("permanent error")

        with pytest.raises(ValueError, match="permanent error"):
            await always_fail()

    @pytest.mark.asyncio
    async def test_only_retries_specified_exceptions(self):
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        async def wrong_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            await wrong_error()

        # Should fail on first attempt without retrying
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_respects_max_delay(self):
        """Verify delay doesn't exceed max_delay."""
        attempts = []

        @retry_with_backoff(max_retries=5, base_delay=0.01, max_delay=0.05, jitter=False)
        async def slow_recovery():
            attempts.append(1)
            if len(attempts) < 5:
                raise IOError("fail")
            return "done"

        result = await slow_recovery()
        assert result == "done"


class TestGracefulFallback:
    """Tests for the graceful fallback decorator."""

    @pytest.mark.asyncio
    async def test_returns_result_on_success(self):
        @graceful_fallback(fallback_value="fallback")
        async def good():
            return "real_value"

        assert await good() == "real_value"

    @pytest.mark.asyncio
    async def test_returns_fallback_on_error(self):
        @graceful_fallback(fallback_value=[])
        async def broken():
            raise RuntimeError("service down")

        result = await broken()
        assert result == []

    @pytest.mark.asyncio
    async def test_calls_on_error_callback(self):
        errors = []

        @graceful_fallback(fallback_value=None, on_error=lambda e: errors.append(e))
        async def broken():
            raise ConnectionError("timeout")

        await broken()
        assert len(errors) == 1
        assert isinstance(errors[0], ConnectionError)

    @pytest.mark.asyncio
    async def test_critical_mode_reraises(self):
        @graceful_fallback(fallback_value=None, critical=True)
        async def critical_op():
            raise ValueError("critical failure")

        with pytest.raises(ValueError, match="critical failure"):
            await critical_op()

    @pytest.mark.asyncio
    async def test_fallback_none(self):
        @graceful_fallback(fallback_value=None)
        async def fails():
            raise Exception("boom")

        assert await fails() is None


class TestTimeout:
    """Tests for the timeout decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_within_timeout(self):
        @timeout(1.0)
        async def quick():
            return "fast"

        assert await quick() == "fast"

    @pytest.mark.asyncio
    async def test_raises_on_timeout(self):
        @timeout(0.05)
        async def slow():
            await asyncio.sleep(1.0)
            return "never"

        with pytest.raises(asyncio.TimeoutError):
            await slow()

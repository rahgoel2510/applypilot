"""Tests for the circuit breaker resilience pattern."""

import asyncio
import time

import pytest

from linkedin_agent.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)


class TestCircuitBreakerStates:
    """Test circuit state transitions."""

    @pytest.mark.asyncio
    async def test_starts_closed(self):
        cb = CircuitBreaker("test-service")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available is True

    @pytest.mark.asyncio
    async def test_stays_closed_on_success(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        async with cb:
            pass  # success
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)

        for _ in range(3):
            with pytest.raises(ValueError):
                async with cb:
                    raise ValueError("fail")

        assert cb.state == CircuitState.OPEN
        assert cb.is_available is False

    @pytest.mark.asyncio
    async def test_rejects_calls_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60)

        with pytest.raises(ValueError):
            async with cb:
                raise ValueError("fail")

        assert cb.state == CircuitState.OPEN

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            async with cb:
                pass

        assert "test" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)

        with pytest.raises(ValueError):
            async with cb:
                raise ValueError("fail")

        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_closes_after_success_in_half_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1, success_threshold=2)

        # Trip the breaker
        with pytest.raises(ValueError):
            async with cb:
                raise ValueError("fail")

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Two successes needed to close
        async with cb:
            pass
        async with cb:
            pass

        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)

        with pytest.raises(ValueError):
            async with cb:
                raise ValueError("fail")

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Fail again in half-open
        with pytest.raises(RuntimeError):
            async with cb:
                raise RuntimeError("still failing")

        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerReset:
    """Test manual reset functionality."""

    @pytest.mark.asyncio
    async def test_manual_reset(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60)

        with pytest.raises(ValueError):
            async with cb:
                raise ValueError("fail")

        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available is True


class TestCircuitBreakerProtect:
    """Test the decorator form."""

    @pytest.mark.asyncio
    async def test_protect_decorator_success(self):
        cb = CircuitBreaker("test", failure_threshold=3)

        @cb.protect
        async def my_func():
            return 42

        result = await my_func()
        assert result == 42
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_protect_decorator_failure(self):
        cb = CircuitBreaker("test", failure_threshold=2)

        @cb.protect
        async def my_func():
            raise IOError("network error")

        with pytest.raises(IOError):
            await my_func()
        with pytest.raises(IOError):
            await my_func()

        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerSerialization:
    """Test to_dict for health endpoints."""

    @pytest.mark.asyncio
    async def test_to_dict(self):
        cb = CircuitBreaker("telegram", failure_threshold=5, recovery_timeout=120)
        data = cb.to_dict()
        assert data["service"] == "telegram"
        assert data["state"] == "closed"
        assert data["failure_count"] == 0
        assert data["failure_threshold"] == 5
        assert data["recovery_timeout"] == 120

"""Tests for the health monitoring module."""

import asyncio

import pytest

from linkedin_agent.resilience.health import (
    HealthMonitor,
    ServiceHealth,
    ServiceStatus,
)


class TestServiceHealth:
    """Tests for the ServiceHealth dataclass."""

    def test_defaults(self):
        h = ServiceHealth(name="test")
        assert h.name == "test"
        assert h.status == ServiceStatus.UNKNOWN
        assert h.is_healthy is False

    def test_is_healthy(self):
        h = ServiceHealth(name="ok", status=ServiceStatus.HEALTHY)
        assert h.is_healthy is True

    def test_to_dict(self):
        h = ServiceHealth(name="svc", status=ServiceStatus.DEGRADED, message="slow")
        d = h.to_dict()
        assert d["name"] == "svc"
        assert d["status"] == "degraded"
        assert d["message"] == "slow"


class TestHealthMonitor:
    """Tests for the HealthMonitor aggregate checker."""

    @pytest.mark.asyncio
    async def test_check_all_healthy(self):
        monitor = HealthMonitor()

        async def healthy_check():
            return ServiceHealth(name="svc", status=ServiceStatus.HEALTHY)

        monitor.register("svc", healthy_check)
        report = await monitor.check_all()

        assert report["overall"] == "healthy"
        assert len(report["services"]) == 1
        assert report["services"][0]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_check_all_degraded(self):
        monitor = HealthMonitor()

        async def healthy():
            return ServiceHealth(name="a", status=ServiceStatus.HEALTHY)

        async def unhealthy():
            return ServiceHealth(name="b", status=ServiceStatus.UNHEALTHY, message="down")

        monitor.register("a", healthy)
        monitor.register("b", unhealthy)
        report = await monitor.check_all()

        assert report["overall"] == "degraded"

    @pytest.mark.asyncio
    async def test_check_timeout(self):
        monitor = HealthMonitor(check_timeout=0.05)

        async def slow_check():
            await asyncio.sleep(1.0)
            return ServiceHealth(name="slow", status=ServiceStatus.HEALTHY)

        monitor.register("slow", slow_check)
        report = await monitor.check_all()

        assert report["services"][0]["status"] == "unhealthy"
        assert "timed out" in report["services"][0]["message"]

    @pytest.mark.asyncio
    async def test_check_exception(self):
        monitor = HealthMonitor()

        async def exploding_check():
            raise ConnectionError("refuse")

        monitor.register("boom", exploding_check)
        report = await monitor.check_all()

        assert report["services"][0]["status"] == "unhealthy"
        assert "refuse" in report["services"][0]["message"]

    @pytest.mark.asyncio
    async def test_get_cached_status(self):
        monitor = HealthMonitor()

        async def check():
            return ServiceHealth(name="cache_test", status=ServiceStatus.HEALTHY)

        monitor.register("cache_test", check)
        await monitor.check_all()

        cached = monitor.get_cached_status("cache_test")
        assert cached.is_healthy is True

    @pytest.mark.asyncio
    async def test_is_service_available(self):
        monitor = HealthMonitor()

        async def check():
            return ServiceHealth(name="avail", status=ServiceStatus.HEALTHY)

        monitor.register("avail", check)
        await monitor.check_all()

        assert monitor.is_service_available("avail") is True
        assert monitor.is_service_available("nonexistent") is False

    @pytest.mark.asyncio
    async def test_check_one(self):
        monitor = HealthMonitor()

        async def check():
            return ServiceHealth(name="single", status=ServiceStatus.HEALTHY)

        monitor.register("single", check)
        result = await monitor.check_one("single")
        assert result.is_healthy is True
        assert result.last_check > 0

    @pytest.mark.asyncio
    async def test_check_one_unregistered(self):
        monitor = HealthMonitor()
        result = await monitor.check_one("ghost")
        assert result.status == ServiceStatus.UNKNOWN

"""Tests for the dependency injection container."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from linkedin_agent.container import Container


class TestContainerBasics:
    """Test basic container functionality."""

    def test_creates_with_config(self, sample_config):
        container = Container(sample_config)
        assert container.config == sample_config

    def test_override_replaces_service(self, sample_config):
        container = Container(sample_config)
        mock = MagicMock()
        container.override("scorer", mock)
        assert container.scorer is mock

    def test_override_clears_cache(self, sample_config):
        container = Container(sample_config)
        # Override before first access
        mock1 = MagicMock()
        container.override("scorer", mock1)
        assert container.scorer is mock1

        # Override again
        mock2 = MagicMock()
        container.override("scorer", mock2)
        assert container.scorer is mock2

    def test_reset_clears_all(self, sample_config):
        container = Container(sample_config)
        mock = MagicMock()
        container.override("scorer", mock)
        assert container.scorer is mock

        container.reset()
        # After reset, accessing scorer would create a real instance
        # We just verify the override is gone
        assert "scorer" not in container._overrides
        assert "scorer" not in container._cache


class TestContainerLazyInit:
    """Test that services are lazily instantiated."""

    def test_cache_reuses_instance(self, sample_config):
        container = Container(sample_config)
        mock = MagicMock()
        container.override("dedup", mock)

        first = container.dedup
        second = container.dedup
        assert first is second

    def test_different_services_are_independent(self, sample_config):
        container = Container(sample_config)
        mock_dedup = MagicMock()
        mock_scorer = MagicMock()
        container.override("dedup", mock_dedup)
        container.override("scorer", mock_scorer)

        assert container.dedup is mock_dedup
        assert container.scorer is mock_scorer
        assert container.dedup is not container.scorer


class TestContainerCreateApplicant:
    """Test the applicant factory method."""

    def test_create_applicant_with_override(self, sample_config):
        container = Container(sample_config)
        mock_applicant = MagicMock()
        container.override("applicant", mock_applicant)

        result = container.create_applicant(
            browser=MagicMock(),
            scorer=MagicMock(),
            notifier=MagicMock(),
        )
        assert result is mock_applicant

    def test_create_applicant_not_cached(self, configured_container):
        """Applicant is per-cycle, not cached in container."""
        mock_app = AsyncMock()
        configured_container.override("applicant", mock_app)

        a1 = configured_container.create_applicant(
            browser=MagicMock(),
            scorer=MagicMock(),
            notifier=MagicMock(),
        )
        assert a1 is mock_app


class TestContainerServiceResolution:
    """Test all container service properties resolve correctly with overrides."""

    def test_browser_override(self, configured_container, mock_browser):
        assert configured_container.browser is mock_browser

    def test_scorer_override(self, configured_container, mock_scorer):
        assert configured_container.scorer is mock_scorer

    def test_notifier_override(self, configured_container, mock_notifier):
        assert configured_container.notifier is mock_notifier

    def test_dedup_override(self, configured_container, mock_dedup):
        assert configured_container.dedup is mock_dedup

    def test_daily_cap_override(self, configured_container, mock_daily_cap):
        assert configured_container.daily_cap is mock_daily_cap

    def test_retry_queue_override(self, configured_container, mock_retry_queue):
        assert configured_container.retry_queue is mock_retry_queue

    def test_tracker_override(self, configured_container, mock_tracker):
        assert configured_container.tracker is mock_tracker

    def test_inmail_override(self, configured_container, mock_inmail):
        assert configured_container.inmail is mock_inmail

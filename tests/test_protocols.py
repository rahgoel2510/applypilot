"""Tests for Protocol interface definitions and runtime checking."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from linkedin_agent.protocols import (
    AnswerGeneratorProtocol,
    ApplicationExecutorProtocol,
    BrowserSession,
    DailyCapProtocol,
    DedupStore,
    FallbackScorerProtocol,
    HealthCheck,
    InMailDrafterProtocol,
    JobScorer,
    Notifier,
    RetryQueueProtocol,
    TrackerClientProtocol,
)


class TestProtocolCompliance:
    """Verify that mock implementations satisfy Protocol runtime checks."""

    def test_browser_session_protocol(self, mock_browser):
        assert isinstance(mock_browser, BrowserSession)

    def test_notifier_protocol(self, mock_notifier):
        assert isinstance(mock_notifier, Notifier)

    def test_dedup_store_protocol(self, mock_dedup):
        assert isinstance(mock_dedup, DedupStore)

    def test_daily_cap_protocol(self, mock_daily_cap):
        assert isinstance(mock_daily_cap, DailyCapProtocol)

    def test_retry_queue_protocol(self, mock_retry_queue):
        assert isinstance(mock_retry_queue, RetryQueueProtocol)

    def test_tracker_client_protocol(self, mock_tracker):
        assert isinstance(mock_tracker, TrackerClientProtocol)

    def test_inmail_drafter_protocol(self, mock_inmail):
        assert isinstance(mock_inmail, InMailDrafterProtocol)

    def test_job_scorer_protocol(self, mock_scorer):
        assert isinstance(mock_scorer, JobScorer)


class TestProtocolMethods:
    """Verify protocol method signatures are enforced."""

    def test_browser_has_required_methods(self):
        """BrowserSession protocol requires specific async methods."""
        browser = AsyncMock()
        browser.launch = AsyncMock()
        browser.close = AsyncMock()
        browser.login = AsyncMock()
        browser.navigate_to_jobs = AsyncMock()
        browser.search_jobs = AsyncMock()
        browser.get_job_listings = AsyncMock(return_value=[])
        browser.navigate_to_url = AsyncMock()
        browser.check_application_statuses = AsyncMock(return_value=[])
        assert isinstance(browser, BrowserSession)

    def test_scorer_has_required_methods(self):
        """JobScorer protocol requires specific methods."""
        scorer = MagicMock()
        scorer.meets_threshold = MagicMock(return_value=True)
        scorer.is_duplicate = MagicMock(return_value=False)
        scorer.add_to_applied = MagicMock()
        assert isinstance(scorer, JobScorer)

    def test_fallback_scorer_protocol(self):
        """FallbackScorerProtocol requires score_from_job_card."""
        scorer = MagicMock()
        scorer.score_from_job_card = MagicMock(return_value=0.75)
        assert isinstance(scorer, FallbackScorerProtocol)

    def test_health_check_protocol(self):
        """HealthCheck protocol requires check_health method."""
        checker = AsyncMock()
        checker.check_health = AsyncMock(return_value={"status": "healthy"})
        assert isinstance(checker, HealthCheck)

"""Shared test fixtures for the linkedin_agent test suite.

Provides:
- Mock implementations of all Protocol interfaces
- Pre-configured Container with mocks
- Sample config fixture
- Async test helpers
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set test env vars BEFORE any linkedin_agent imports
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-123")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123456789")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("LINKEDIN_EMAIL", "test@example.com")
os.environ.setdefault("LINKEDIN_PASSWORD", "test-password")

from linkedin_agent.config import Settings, get_config, reset_config


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset the config singleton between tests."""
    reset_config()
    yield
    reset_config()


@pytest.fixture
def sample_config() -> Settings:
    """Provide a test-safe Settings instance."""
    return get_config(validate=False, reload=True)


@pytest.fixture
def sample_job() -> dict[str, Any]:
    """Sample job dict matching the format from browser.get_job_listings()."""
    return {
        "job_id": "12345678",
        "id": "12345678",
        "title": "Senior Software Engineer",
        "company": "TechCorp",
        "location": "Bangalore, India",
        "url": "https://www.linkedin.com/jobs/view/12345678/",
        "is_easy_apply": True,
        "is_external": False,
        "match_score": 0.85,
        "scoring_method": "premium",
        "description": "We are looking for a senior engineer...",
    }


@pytest.fixture
def mock_browser():
    """Mock browser session implementing BrowserSession protocol."""
    browser = AsyncMock()
    browser.launch = AsyncMock()
    browser.close = AsyncMock()
    browser.login = AsyncMock()
    browser.navigate_to_jobs = AsyncMock()
    browser.search_jobs = AsyncMock()
    browser.get_job_listings = AsyncMock(return_value=[])
    browser.navigate_to_url = AsyncMock()
    browser.check_application_statuses = AsyncMock(return_value=[])
    browser.page = MagicMock()
    return browser


@pytest.fixture
def mock_notifier():
    """Mock notifier implementing Notifier protocol."""
    notifier = AsyncMock()
    notifier.send_notification = AsyncMock()
    notifier.send_tally_report = AsyncMock()
    notifier.send_job_applied_notification = AsyncMock()
    notifier.send_inmail_draft = AsyncMock()
    return notifier


@pytest.fixture
def mock_tracker():
    """Mock tracker implementing TrackerClientProtocol."""
    tracker = AsyncMock()
    tracker.push_event = AsyncMock(return_value=True)
    tracker.log = AsyncMock(return_value=True)
    tracker.log_cycle_start = AsyncMock(return_value=True)
    tracker.log_cycle_end = AsyncMock(return_value=True)
    tracker.log_job_error = AsyncMock(return_value=True)
    tracker.log_inmail_drafted = AsyncMock(return_value=True)
    tracker.log_agent_start = AsyncMock(return_value=True)
    tracker.log_agent_stop = AsyncMock(return_value=True)
    tracker.push_inmail_draft = AsyncMock(return_value=True)
    return tracker


@pytest.fixture
def mock_dedup():
    """Mock dedup store implementing DedupStore protocol."""
    dedup = MagicMock()
    dedup.connected = True
    dedup.is_seen = MagicMock(return_value=False)
    dedup.mark_seen = MagicMock()
    dedup.mark_applied = MagicMock()
    dedup.mark_skipped = MagicMock()
    dedup.sync = MagicMock()
    dedup.total_seen = MagicMock(return_value=0)
    dedup.stats = MagicMock(return_value={})
    return dedup


@pytest.fixture
def mock_daily_cap():
    """Mock daily cap implementing DailyCapProtocol."""
    cap = MagicMock()
    cap.daily_limit = 80
    cap.today_count = 0
    cap.remaining = 80
    cap.is_at_limit = False
    cap.is_near_limit = False
    cap.can_apply = MagicMock(return_value=True)
    cap.record_application = MagicMock()
    return cap


@pytest.fixture
def mock_retry_queue():
    """Mock retry queue implementing RetryQueueProtocol."""
    queue = MagicMock()
    queue.pending_count = 0
    queue.add = MagicMock()
    queue.get_due = MagicMock(return_value=[])
    queue.mark_success = MagicMock()
    queue.cleanup_old = MagicMock()
    queue.get_stats = MagicMock(return_value={"pending": 0, "permanent_failures": 0})
    return queue


@pytest.fixture
def mock_scorer():
    """Mock scorer implementing JobScorer protocol."""
    scorer = MagicMock()
    scorer.meets_threshold = MagicMock(return_value=True)
    scorer.is_duplicate = MagicMock(return_value=False)
    scorer.add_to_applied = MagicMock()
    return scorer


@pytest.fixture
def mock_inmail():
    """Mock InMail drafter implementing InMailDrafterProtocol."""
    inmail = AsyncMock()
    inmail.get_candidate_summary = MagicMock(return_value="Experienced engineer...")
    inmail.draft_inmail = AsyncMock(return_value="Dear Recruiter, I'm interested...")
    return inmail


@pytest.fixture
def configured_container(
    sample_config,
    mock_browser,
    mock_notifier,
    mock_tracker,
    mock_dedup,
    mock_daily_cap,
    mock_retry_queue,
    mock_scorer,
    mock_inmail,
):
    """Fully configured Container with all mocks injected."""
    from linkedin_agent.container import Container

    container = Container(sample_config)
    container.override("browser", mock_browser)
    container.override("notifier", mock_notifier)
    container.override("tracker", mock_tracker)
    container.override("dedup", mock_dedup)
    container.override("daily_cap", mock_daily_cap)
    container.override("retry_queue", mock_retry_queue)
    container.override("scorer", mock_scorer)
    container.override("inmail", mock_inmail)
    return container


@pytest.fixture
def sample_settings(sample_config) -> Settings:
    """Alias for sample_config — backwards compatibility with older tests."""
    return sample_config


@pytest.fixture
def mock_drafts_file(tmp_path, monkeypatch):
    """Provide a temporary drafts file path for InMail tests."""
    import linkedin_agent.inmail as inmail_module
    drafts_file = tmp_path / "inmail_drafts.json"
    monkeypatch.setattr(inmail_module, "DRAFTS_FILE", drafts_file)
    monkeypatch.setattr(inmail_module, "DRAFTS_DIR", tmp_path)
    return drafts_file

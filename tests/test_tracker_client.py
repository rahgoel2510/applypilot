"""Tests for the tracker HTTP client module."""

from unittest.mock import AsyncMock, patch

import pytest

from linkedin_agent.tracker_client import TrackerClient


@pytest.fixture
def tracker():
    """Create a TrackerClient for testing."""
    return TrackerClient(base_url="http://127.0.0.1:8000/api", timeout=2.0)


class TestTrackerClientInit:
    """Tests for TrackerClient initialization."""

    def test_default_url(self):
        t = TrackerClient()
        assert "127.0.0.1:8000" in t._base_url

    def test_custom_url(self):
        t = TrackerClient(base_url="http://custom:9000/api")
        assert t._base_url == "http://custom:9000/api"

    def test_strips_trailing_slash(self):
        t = TrackerClient(base_url="http://host/api/")
        assert not t._base_url.endswith("/")


class TestTrackerClientPushEvent:
    """Tests for push_event method."""

    @pytest.mark.asyncio
    async def test_push_event_calls_post(self, tracker):
        with patch.object(tracker, "_post", new_callable=AsyncMock, return_value=True) as mock_post:
            result = await tracker.push_event(
                event="submitted",
                title="SWE",
                company="Corp",
                location="Bangalore",
                match_score=0.85,
            )
            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "submitted" in str(call_args)

    @pytest.mark.asyncio
    async def test_push_event_handles_failure(self, tracker):
        with patch.object(tracker, "_post", new_callable=AsyncMock, return_value=False):
            result = await tracker.push_event(
                event="submitted",
                title="SWE",
                company="Corp",
            )
            assert result is False


class TestTrackerClientLog:
    """Tests for log method."""

    @pytest.mark.asyncio
    async def test_log_calls_post(self, tracker):
        with patch.object(tracker, "_post", new_callable=AsyncMock, return_value=True) as mock_post:
            result = await tracker.log(
                event_type="cycle_start",
                severity="info",
                message="Starting scan",
            )
            assert result is True


class TestTrackerClientConvenience:
    """Tests for convenience methods."""

    @pytest.mark.asyncio
    async def test_log_cycle_start(self, tracker):
        with patch.object(tracker, "log", new_callable=AsyncMock, return_value=True):
            result = await tracker.log_cycle_start(max_postings=50, collection="Recommended")
            assert result is True

    @pytest.mark.asyncio
    async def test_log_cycle_end(self, tracker):
        with patch.object(tracker, "log", new_callable=AsyncMock, return_value=True):
            result = await tracker.log_cycle_end(
                submitted=5, skipped=10, paused=2, errors=1, duration_sec=120
            )
            assert result is True


class TestTrackerClientJobError:
    """Tests for job error logging."""

    @pytest.mark.asyncio
    async def test_log_job_error(self, tracker):
        with patch.object(tracker, "log", new_callable=AsyncMock, return_value=True):
            result = await tracker.log_job_error(
                title="SWE", company="Corp", error="timeout"
            )
            assert result is True


class TestTrackerClientInMail:
    """Tests for InMail draft pushing."""

    @pytest.mark.asyncio
    async def test_push_inmail_draft(self, tracker):
        with patch.object(tracker, "_post", new_callable=AsyncMock, return_value=True):
            result = await tracker.push_inmail_draft(
                job_title="SWE",
                company="Google",
                recruiter="Jane",
                draft_text="Dear Jane...",
                job_id="123",
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_log_inmail_drafted(self, tracker):
        with patch.object(tracker, "log", new_callable=AsyncMock, return_value=True):
            result = await tracker.log_inmail_drafted(
                title="SWE", company="Google", recruiter="Jane"
            )
            assert result is True


class TestTrackerClientAgentLifecycle:
    """Tests for agent start/stop logging."""

    @pytest.mark.asyncio
    async def test_log_agent_start(self, tracker):
        with patch.object(tracker, "log", new_callable=AsyncMock, return_value=True):
            result = await tracker.log_agent_start(
                interval_minutes=30, active_hours="9:00–22:00"
            )
            assert result is True


class TestTrackerClientPost:
    """Tests for the internal _post method."""

    @pytest.mark.asyncio
    async def test_post_handles_connection_error(self, tracker):
        """_post returns False on connection error."""
        result = await tracker._post(
            "http://127.0.0.1:59999/nonexistent",  # Invalid port
            {"test": "data"},
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_post_handles_timeout(self, tracker):
        """_post returns False on timeout."""
        # Use a non-routable address to force timeout
        slow_tracker = TrackerClient(base_url="http://192.0.2.1:8000/api", timeout=0.1)
        result = await slow_tracker._post(
            "http://192.0.2.1:8000/api/test",
            {"test": "data"},
        )
        assert result is False

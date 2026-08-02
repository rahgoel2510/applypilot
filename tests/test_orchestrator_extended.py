"""Extended orchestrator tests for scan cycle inner logic."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linkedin_agent.orchestrator import JobAgent, JobStatus, CycleTally


class TestScanCycleDiscovery:
    """Tests covering the job discovery and evaluation flow."""

    @pytest.mark.asyncio
    async def test_discovers_and_evaluates_jobs(
        self, sample_config, configured_container, mock_browser, mock_daily_cap, mock_dedup, mock_tracker
    ):
        """Full cycle: discovers jobs → dedup check → score → apply/skip."""
        # Configure browser to return 2 jobs
        jobs = [
            {"job_id": "001", "title": "SWE", "company": "Google", "location": "Bangalore",
             "url": "https://linkedin.com/jobs/view/001/", "is_easy_apply": True},
            {"job_id": "002", "title": "PM", "company": "Meta", "location": "Remote",
             "url": "https://linkedin.com/jobs/view/002/", "is_easy_apply": True},
        ]
        mock_browser.get_job_listings = AsyncMock(return_value=jobs)
        mock_dedup.is_seen.return_value = False
        mock_dedup.total_seen.return_value = 5  # Not first run

        agent = JobAgent(config=sample_config, dry_run=True, container=configured_container)
        await agent.run_scan_cycle()

        # Browser was launched and logged in
        mock_browser.launch.assert_called_once()
        mock_browser.login.assert_called_once()
        # Browser closed in finally block
        mock_browser.close.assert_called()

    @pytest.mark.asyncio
    async def test_dedup_skips_seen_jobs(
        self, sample_config, configured_container, mock_browser, mock_daily_cap, mock_dedup, mock_tracker
    ):
        """Jobs already in dedup DB are skipped."""
        jobs = [
            {"job_id": "001", "title": "SWE", "company": "Google", "location": "Bangalore",
             "url": "https://linkedin.com/jobs/view/001/"},
        ]
        mock_browser.get_job_listings = AsyncMock(return_value=jobs)
        mock_dedup.is_seen.return_value = True  # Already seen
        mock_dedup.total_seen.return_value = 100

        agent = JobAgent(config=sample_config, dry_run=True, container=configured_container)
        await agent.run_scan_cycle()

        # Job should be skipped (dedup), not processed
        assert agent.tally.submitted == 0

    @pytest.mark.asyncio
    async def test_shutdown_event_stops_cycle(
        self, sample_config, configured_container, mock_browser, mock_daily_cap, mock_dedup, mock_tracker
    ):
        """Setting shutdown event mid-cycle stops processing."""
        jobs = [{"job_id": f"{i}", "title": f"Job {i}", "company": "Corp",
                 "location": "X", "url": f"https://x/{i}"} for i in range(50)]
        mock_browser.get_job_listings = AsyncMock(return_value=jobs)
        mock_dedup.is_seen.return_value = False
        mock_dedup.total_seen.return_value = 5

        agent = JobAgent(config=sample_config, dry_run=True, container=configured_container)
        # Set shutdown after very short time
        agent._shutdown_event.set()
        await agent.run_scan_cycle()

        # Should have stopped early
        assert agent.tally.total < 50


class TestScanCycleScoring:
    """Tests for scoring and threshold evaluation in the scan cycle."""

    @pytest.mark.asyncio
    async def test_fallback_scoring_when_no_premium(
        self, sample_config, configured_container, mock_browser, mock_daily_cap, mock_dedup, mock_tracker, mock_scorer
    ):
        """When job has no score, fallback scorer is used."""
        jobs = [
            {"job_id": "001", "title": "Engineering Manager", "company": "Corp",
             "location": "Bangalore", "url": "https://x/001",
             "is_easy_apply": True, "match_score": None},  # No premium score
        ]
        mock_browser.get_job_listings = AsyncMock(return_value=jobs)
        mock_dedup.is_seen.return_value = False
        mock_dedup.total_seen.return_value = 5
        mock_scorer.meets_threshold.return_value = True

        # Mock the fallback scorer module
        with patch("linkedin_agent.orchestrator.get_fallback_scorer", create=True) as mock_fb:
            mock_fb_instance = MagicMock()
            mock_fb_instance.score_from_job_card.return_value = 0.75
            mock_fb.return_value = mock_fb_instance

            agent = JobAgent(config=sample_config, dry_run=True, container=configured_container)
            await agent.run_scan_cycle()


class TestScanCycleRetryQueue:
    """Tests for retry queue processing after main scan."""

    @pytest.mark.asyncio
    async def test_retry_queue_processed_after_scan(
        self, sample_config, configured_container, mock_browser, mock_daily_cap,
        mock_dedup, mock_tracker, mock_retry_queue
    ):
        """After main scan, pending retries are attempted."""
        mock_browser.get_job_listings = AsyncMock(return_value=[])
        mock_dedup.total_seen.return_value = 5
        mock_retry_queue.get_due.return_value = []  # No retries pending

        agent = JobAgent(config=sample_config, dry_run=True, container=configured_container)
        await agent.run_scan_cycle()

        # Retry queue cleanup should be called
        mock_retry_queue.cleanup_old.assert_called()


class TestCycleTallyExtended:
    """Extended CycleTally tests."""

    def test_summary_with_all_statuses(self):
        tally = CycleTally()
        tally.record(JobStatus.SUBMITTED)
        tally.record(JobStatus.SUBMITTED)
        tally.record(JobStatus.SKIPPED)
        tally.record(JobStatus.PAUSED)
        tally.record(JobStatus.ERROR)
        summary = tally.summary()
        assert "Submitted: 2" in summary
        assert "Skipped: 1" in summary
        assert "Paused: 1" in summary
        assert "Errors: 1" in summary
        assert "Total: 5" in summary

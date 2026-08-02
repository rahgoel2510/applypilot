"""Tests for the orchestrator (JobAgent) using DI container mocks."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linkedin_agent.orchestrator import CycleTally, JobAgent, JobStatus


class TestCycleTally:
    """Tests for CycleTally data tracking."""

    def test_initial_state(self):
        tally = CycleTally()
        assert tally.submitted == 0
        assert tally.skipped == 0
        assert tally.paused == 0
        assert tally.errors == 0
        assert tally.total == 0

    def test_record_submitted(self):
        tally = CycleTally()
        tally.record(JobStatus.SUBMITTED)
        assert tally.submitted == 1
        assert tally.total == 1

    def test_record_skipped(self):
        tally = CycleTally()
        tally.record(JobStatus.SKIPPED)
        assert tally.skipped == 1
        assert tally.total == 1

    def test_record_paused(self):
        tally = CycleTally()
        tally.record(JobStatus.PAUSED)
        assert tally.paused == 1

    def test_record_error(self):
        tally = CycleTally()
        tally.record(JobStatus.ERROR)
        assert tally.errors == 1

    def test_record_multiple(self):
        tally = CycleTally()
        tally.record(JobStatus.SUBMITTED)
        tally.record(JobStatus.SUBMITTED)
        tally.record(JobStatus.SKIPPED)
        tally.record(JobStatus.ERROR)
        assert tally.total == 4
        assert tally.submitted == 2
        assert tally.skipped == 1
        assert tally.errors == 1

    def test_summary_format(self):
        tally = CycleTally()
        tally.record(JobStatus.SUBMITTED)
        summary = tally.summary()
        assert "Submitted: 1" in summary
        assert "Total: 1" in summary


class TestJobAgentInit:
    """Tests for JobAgent initialization."""

    def test_init_with_container(self, sample_config, configured_container):
        agent = JobAgent(
            config=sample_config,
            dry_run=True,
            container=configured_container,
        )
        assert agent.dry_run is True
        assert agent.config is sample_config
        assert agent.browser is configured_container.browser
        assert agent.matcher is configured_container.scorer
        assert agent.notifier is configured_container.notifier

    def test_init_dry_run_mode(self, sample_config, configured_container):
        agent = JobAgent(config=sample_config, dry_run=True, container=configured_container)
        assert agent.dry_run is True

    def test_init_applies_container_services(self, sample_config, configured_container):
        agent = JobAgent(config=sample_config, container=configured_container)
        # Verify all services come from container
        assert agent.tracker is configured_container.tracker
        assert agent.retry_queue is configured_container.retry_queue
        assert agent.daily_cap is configured_container.daily_cap


class TestJobAgentShutdown:
    """Tests for graceful shutdown."""

    @pytest.mark.asyncio
    async def test_request_shutdown_sets_event(self, sample_config, configured_container):
        agent = JobAgent(config=sample_config, container=configured_container)
        assert not agent._shutdown_event.is_set()
        agent.request_shutdown()
        assert agent._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_closes_browser(self, sample_config, configured_container, mock_browser):
        agent = JobAgent(config=sample_config, container=configured_container)
        await agent.shutdown()
        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_notifies_telegram(self, sample_config, configured_container, mock_notifier):
        agent = JobAgent(config=sample_config, container=configured_container)
        await agent.shutdown()
        mock_notifier.send_notification.assert_called()


class TestJobAgentProcessJob:
    """Tests for individual job processing logic."""

    @pytest.mark.asyncio
    async def test_skip_external_when_configured(self, sample_config, configured_container):
        from dataclasses import replace
        from linkedin_agent.config import JobSearchConfig

        new_js = replace(sample_config.job_search, skip_external_apply=True)
        config = replace(sample_config, job_search=new_js)
        configured_container._config = config

        agent = JobAgent(config=config, dry_run=True, container=configured_container)

        job = {"title": "SWE", "company": "Corp", "is_external": True, "id": "123"}
        result = await agent.process_job(job)
        assert result.status == "skipped_external"

    @pytest.mark.asyncio
    async def test_skip_duplicate(self, sample_config, configured_container, mock_scorer):
        mock_scorer.is_duplicate.return_value = True
        agent = JobAgent(config=sample_config, dry_run=True, container=configured_container)

        job = {"title": "SWE", "company": "Corp", "id": "123"}
        result = await agent.process_job(job)
        assert result.status == "duplicate"

    @pytest.mark.asyncio
    async def test_dry_run_would_apply_high_score(self, sample_config, configured_container, mock_scorer):
        mock_scorer.is_duplicate.return_value = False
        mock_scorer.meets_threshold.return_value = True
        agent = JobAgent(config=sample_config, dry_run=True, container=configured_container)

        job = {"title": "SWE", "company": "Corp", "id": "123", "match_score": 0.9}
        result = await agent.process_job(job)
        assert result.status == "submitted"

    @pytest.mark.asyncio
    async def test_dry_run_would_skip_low_score(self, sample_config, configured_container, mock_scorer):
        mock_scorer.is_duplicate.return_value = False
        mock_scorer.meets_threshold.return_value = False
        agent = JobAgent(config=sample_config, dry_run=True, container=configured_container)

        job = {"title": "SWE", "company": "Corp", "id": "123", "match_score": 0.3}
        result = await agent.process_job(job)
        assert result.status == "skipped_threshold"


class TestJobAgentReportTally:
    """Tests for tally reporting."""

    @pytest.mark.asyncio
    async def test_report_tally_with_metrics(self, sample_config, configured_container, mock_notifier):
        agent = JobAgent(config=sample_config, container=configured_container)
        metrics = {
            "total_found": 50,
            "dedup_skipped": 10,
            "new_discovered": 40,
            "applied": 5,
            "external_manual": 3,
            "skipped_low_score": 32,
            "paused": 0,
            "errors": 0,
        }
        await agent.report_tally(full_metrics=metrics)
        mock_notifier.send_tally_report.assert_called_once()
        call_args = mock_notifier.send_tally_report.call_args[0][0]
        assert call_args["submitted"] == 5
        assert call_args["total_found"] == 50

    @pytest.mark.asyncio
    async def test_report_tally_legacy_format(self, sample_config, configured_container, mock_notifier):
        agent = JobAgent(config=sample_config, container=configured_container)
        agent.tally.record(JobStatus.SUBMITTED)
        agent.tally.record(JobStatus.SUBMITTED)
        await agent.report_tally(full_metrics=None)
        mock_notifier.send_tally_report.assert_called_once()
        call_args = mock_notifier.send_tally_report.call_args[0][0]
        assert call_args["submitted"] == 2


class TestJobStatusMapping:
    """Tests for the status mapping helper."""

    def test_map_submitted(self):
        assert JobAgent._map_result_status("submitted") == JobStatus.SUBMITTED

    def test_map_paused(self):
        assert JobAgent._map_result_status("paused") == JobStatus.PAUSED

    def test_map_skipped_threshold(self):
        assert JobAgent._map_result_status("skipped_threshold") == JobStatus.SKIPPED

    def test_map_duplicate(self):
        assert JobAgent._map_result_status("duplicate") == JobStatus.SKIPPED

    def test_map_unknown_defaults_to_error(self):
        assert JobAgent._map_result_status("unknown_status") == JobStatus.ERROR


class TestJobAgentScanCycle:
    """Tests for the full scan cycle orchestration."""

    @pytest.mark.asyncio
    async def test_scan_cycle_skips_at_daily_cap(
        self, sample_config, configured_container, mock_daily_cap, mock_notifier, mock_tracker
    ):
        """When daily cap is reached, cycle is skipped entirely."""
        mock_daily_cap.is_at_limit = True
        mock_daily_cap.today_count = 80
        mock_daily_cap.daily_limit = 80

        agent = JobAgent(config=sample_config, container=configured_container)
        await agent.run_scan_cycle()

        # Should notify about cap reached
        mock_notifier.send_notification.assert_called()
        notif_text = str(mock_notifier.send_notification.call_args)
        assert "cap" in notif_text.lower() or "80" in notif_text

    @pytest.mark.asyncio
    async def test_scan_cycle_handles_browser_failure(
        self, sample_config, configured_container, mock_browser, mock_notifier, mock_tracker
    ):
        """When browser fails to launch, cycle handles error gracefully."""
        mock_browser.launch.side_effect = Exception("Browser crash")

        agent = JobAgent(config=sample_config, container=configured_container)
        # Should not raise
        await agent.run_scan_cycle()

        # Error should be reported
        mock_tracker.log.assert_called()

    @pytest.mark.asyncio
    async def test_run_once_calls_cycle_and_shutdown(
        self, sample_config, configured_container, mock_browser, mock_daily_cap
    ):
        """run_once() calls run_scan_cycle + shutdown."""
        mock_daily_cap.is_at_limit = True  # Skip actual scanning

        agent = JobAgent(config=sample_config, container=configured_container)
        await agent.run_once()

        # Browser should be closed (shutdown)
        mock_browser.close.assert_called()


class TestJobAgentDaemon:
    """Tests for daemon mode."""

    @pytest.mark.asyncio
    async def test_daemon_stops_on_shutdown_event(
        self, sample_config, configured_container, mock_notifier, mock_tracker, mock_daily_cap
    ):
        """Daemon exits when shutdown is requested."""
        mock_daily_cap.is_at_limit = True  # Skip scanning

        agent = JobAgent(config=sample_config, container=configured_container)
        # Pre-set shutdown event to stop immediately
        agent._shutdown_event.set()

        await agent.run_daemon()

        # Should have attempted to notify about daemon start
        mock_notifier.send_notification.assert_called()


class TestJobAgentInMail:
    """Tests for InMail drafting integration."""

    @pytest.mark.asyncio
    async def test_send_inmail_for_job(
        self, sample_config, configured_container, mock_inmail, mock_notifier, mock_tracker
    ):
        """InMail drafting calls the InMailDrafter and notifier."""
        agent = JobAgent(config=sample_config, container=configured_container)

        job = {
            "title": "Engineering Manager",
            "company": "Google",
            "description": "Lead a team...",
            "recruiter": "Jane Smith",
            "job_id": "123",
        }

        await agent.send_inmail_for_job(job)

        mock_inmail.draft_inmail.assert_called_once()
        mock_notifier.send_inmail_draft.assert_called_once()
        mock_tracker.push_inmail_draft.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_inmail_handles_failure(
        self, sample_config, configured_container, mock_inmail, mock_notifier
    ):
        """InMail failure doesn't crash the agent."""
        mock_inmail.draft_inmail.side_effect = Exception("AI error")

        agent = JobAgent(config=sample_config, container=configured_container)
        job = {"title": "SWE", "company": "Corp", "description": ""}

        # Should not raise
        await agent.send_inmail_for_job(job)


class TestJobAgentCheckResponses:
    """Tests for application status checking."""

    @pytest.mark.asyncio
    async def test_check_response_statuses(
        self, sample_config, configured_container, mock_browser, mock_tracker
    ):
        """Response status checks push updates to tracker."""
        mock_browser.check_application_statuses.return_value = [
            {"job_id": "111", "title": "SWE", "company": "Corp", "status": "viewed by employer"},
        ]

        agent = JobAgent(config=sample_config, container=configured_container)
        await agent.check_response_statuses()

        mock_tracker.push_event.assert_called()

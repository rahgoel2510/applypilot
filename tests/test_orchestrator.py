"""Unit tests for linkedin_agent.orchestrator module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linkedin_agent.orchestrator import CycleTally, JobAgent, JobStatus


# ===========================================================================
# CycleTally
# ===========================================================================


class TestCycleTally:
    """Tests for the CycleTally counter."""

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
        assert tally.total == 1

    def test_record_error(self):
        tally = CycleTally()
        tally.record(JobStatus.ERROR)
        assert tally.errors == 1
        assert tally.total == 1

    def test_record_multiple(self):
        tally = CycleTally()
        tally.record(JobStatus.SUBMITTED)
        tally.record(JobStatus.SUBMITTED)
        tally.record(JobStatus.SKIPPED)
        tally.record(JobStatus.ERROR)
        assert tally.submitted == 2
        assert tally.skipped == 1
        assert tally.errors == 1
        assert tally.total == 4

    def test_summary_format(self):
        tally = CycleTally()
        tally.record(JobStatus.SUBMITTED)
        summary = tally.summary()
        assert "Submitted: 1" in summary
        assert "Total: 1" in summary


# ===========================================================================
# JobStatus mapping
# ===========================================================================


class TestStatusMapping:
    """Tests for _map_result_status."""

    @pytest.mark.parametrize(
        "input_status,expected",
        [
            ("submitted", JobStatus.SUBMITTED),
            ("paused", JobStatus.PAUSED),
            ("skipped_threshold", JobStatus.SKIPPED),
            ("skipped_external", JobStatus.SKIPPED),
            ("duplicate", JobStatus.SKIPPED),
            ("error", JobStatus.ERROR),
            ("unknown_status", JobStatus.ERROR),  # unmapped → error
        ],
    )
    def test_mapping(self, input_status, expected):
        assert JobAgent._map_result_status(input_status) == expected


# ===========================================================================
# JobAgent pipeline logic
# ===========================================================================


class TestJobAgentProcessJob:
    """Tests for JobAgent.process_job with mocked sub-modules."""

    @pytest.fixture
    def agent(self, sample_settings):
        """Create a JobAgent with all sub-modules mocked."""
        with patch("linkedin_agent.orchestrator.BrowserManager"), \
             patch("linkedin_agent.orchestrator.TelegramNotifier"), \
             patch("linkedin_agent.orchestrator.InMailDrafter"), \
             patch("linkedin_agent.orchestrator.setup_logging"):
            agent = JobAgent(config=sample_settings)
            # Mock the notifier
            agent.notifier = AsyncMock()
            agent.inmail = AsyncMock()
            agent.browser = AsyncMock()
            return agent

    @pytest.mark.asyncio
    async def test_skip_external_apply(self, agent, sample_job_external):
        """External jobs are skipped immediately."""
        # Need to set up a fake applicant so we can call process_job
        agent._applicant = AsyncMock()
        result = await agent.process_job(sample_job_external)
        assert result.status == "skipped_external"
        # ApplicationExecutor should NOT have been called
        agent._applicant.apply_to_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_duplicate(self, agent, sample_job, mock_applied_file):
        """Duplicate jobs are skipped."""
        agent._applicant = AsyncMock()
        # Pre-mark as applied
        agent.matcher.add_to_applied("TechCorp", "Senior Backend Engineer")

        result = await agent.process_job(sample_job)
        assert result.status == "duplicate"
        agent._applicant.apply_to_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_applies_to_valid_job(self, agent, sample_job, mock_applied_file):
        """Valid job goes to ApplicationExecutor."""
        from linkedin_agent.applicant import ApplicationResult

        mock_result = ApplicationResult(
            status="submitted",
            job_id="job-12345",
            title="Senior Backend Engineer",
            company="TechCorp",
            location="Bangalore, India",
            match_score=0.85,
        )
        agent._applicant = AsyncMock()
        agent._applicant.apply_to_job = AsyncMock(return_value=mock_result)

        result = await agent.process_job(sample_job)
        assert result.status == "submitted"
        agent._applicant.apply_to_job.assert_called_once_with(sample_job)

    @pytest.mark.asyncio
    async def test_dedup_added_on_submit(self, agent, sample_job, mock_applied_file):
        """Successful submit adds the job to dedup set."""
        from linkedin_agent.applicant import ApplicationResult

        mock_result = ApplicationResult(
            status="submitted",
            job_id="job-12345",
            title="Senior Backend Engineer",
            company="TechCorp",
            location="Bangalore, India",
        )
        agent._applicant = AsyncMock()
        agent._applicant.apply_to_job = AsyncMock(return_value=mock_result)

        await agent.process_job(sample_job)

        # Now it should be a duplicate
        assert agent.matcher.is_duplicate("TechCorp", "Senior Backend Engineer") is True

    @pytest.mark.asyncio
    async def test_process_job_without_executor_raises(self, agent, sample_job, mock_applied_file):
        """Calling process_job before run_scan_cycle raises RuntimeError."""
        agent._applicant = None
        with pytest.raises(RuntimeError, match="ApplicationExecutor not initialized"):
            await agent.process_job(sample_job)


# ===========================================================================
# Shutdown logic
# ===========================================================================


class TestShutdown:
    """Tests for shutdown and signal handling."""

    def test_request_shutdown_sets_event(self, sample_settings):
        with patch("linkedin_agent.orchestrator.BrowserManager"), \
             patch("linkedin_agent.orchestrator.TelegramNotifier"), \
             patch("linkedin_agent.orchestrator.InMailDrafter"), \
             patch("linkedin_agent.orchestrator.setup_logging"):
            agent = JobAgent(config=sample_settings)
            assert not agent._shutdown_event.is_set()
            agent.request_shutdown()
            assert agent._shutdown_event.is_set()

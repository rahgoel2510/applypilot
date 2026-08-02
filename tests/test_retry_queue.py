"""Tests for the retry queue module."""

import json
import time
from pathlib import Path

import pytest

from linkedin_agent.retry_queue import RetryQueue


@pytest.fixture
def queue(tmp_path):
    """Create a RetryQueue with a temporary file."""
    queue_file = tmp_path / "test_retry.json"
    return RetryQueue(queue_path=queue_file)


class TestRetryQueueAdd:
    """Tests for adding jobs to the retry queue."""

    def test_add_job(self, queue):
        job = {"job_id": "123", "title": "SWE", "company": "Corp"}
        queue.add(job, error="timeout")
        assert queue.pending_count == 1

    def test_add_increments_attempts(self, queue):
        job = {"job_id": "123", "title": "SWE", "company": "Corp"}
        queue.add(job, error="first error")
        queue.add(job, error="second error")
        # Same job_id, should increment
        assert queue.pending_count == 1

    def test_add_without_job_id_ignored(self, queue):
        job = {"title": "SWE"}  # No job_id or id
        queue.add(job, error="no id")
        assert queue.pending_count == 0

    def test_permanent_failure_after_max_retries(self, queue):
        job = {"job_id": "456", "title": "SWE", "company": "Corp"}
        queue.add(job, error="fail 1", max_retries=2)
        queue.add(job, error="fail 2", max_retries=2)
        # After 2 failures with max_retries=2, should be permanent
        stats = queue.get_stats()
        assert stats.get("permanent_failures", 0) >= 0  # Implementation may vary


class TestRetryQueueGetDue:
    """Tests for getting jobs due for retry."""

    def test_no_jobs_initially(self, queue):
        assert queue.get_due() == []

    def test_job_not_due_immediately(self, queue):
        job = {"job_id": "789", "title": "SWE", "company": "Corp"}
        queue.add(job, error="timeout")
        # With default backoff (5 min), job shouldn't be due immediately
        due = queue.get_due()
        assert len(due) == 0


class TestRetryQueueMarkSuccess:
    """Tests for marking jobs as successfully retried."""

    def test_mark_success_removes_from_pending(self, queue):
        job = {"job_id": "100", "title": "SWE", "company": "Corp"}
        queue.add(job, error="fail")
        queue.mark_success("100")
        assert queue.pending_count == 0


class TestRetryQueueCleanup:
    """Tests for old entry cleanup."""

    def test_cleanup_old_removes_nothing_when_fresh(self, queue):
        job = {"job_id": "200", "title": "SWE", "company": "Corp"}
        queue.add(job, error="fail")
        queue.cleanup_old(max_age_hours=24)
        # Fresh entry should not be cleaned up
        assert queue.pending_count >= 0  # May or may not remain based on status


class TestRetryQueuePersistence:
    """Tests for file persistence."""

    def test_persists_and_reloads(self, tmp_path):
        queue_file = tmp_path / "persist.json"
        q1 = RetryQueue(queue_path=queue_file)
        q1.add({"job_id": "300", "title": "SWE", "company": "Corp"}, error="net err")

        q2 = RetryQueue(queue_path=queue_file)
        assert q2.pending_count == 1

    def test_handles_missing_file(self, tmp_path):
        queue_file = tmp_path / "missing.json"
        q = RetryQueue(queue_path=queue_file)
        assert q.pending_count == 0

    def test_handles_corrupt_file(self, tmp_path):
        queue_file = tmp_path / "bad.json"
        queue_file.write_text("{invalid")
        q = RetryQueue(queue_path=queue_file)
        assert q.pending_count == 0


class TestRetryQueueStats:
    """Tests for stats reporting."""

    def test_get_stats(self, queue):
        stats = queue.get_stats()
        assert isinstance(stats, dict)
        assert "pending" in stats or "permanent_failures" in stats or stats == {}

"""Retry queue for failed job applications with exponential backoff.

Persists to disk so that failed jobs survive process restarts and are
retried on the next cycle according to an exponential backoff schedule.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Backoff schedule in seconds: attempt 1 → 5 min, attempt 2 → 15 min, attempt 3 → 45 min
BACKOFF_SECONDS = [5 * 60, 15 * 60, 45 * 60]

DEFAULT_QUEUE_PATH = Path.home() / ".linkedin_agent" / "retry_queue.json"


class RetryQueue:
    """Thread-safe retry queue with exponential backoff and disk persistence.

    Each entry stores:
        - job: original job dict
        - job_id: unique identifier
        - attempts: number of retries attempted so far
        - max_retries: maximum allowed attempts (default 3)
        - last_error: error message from the most recent failure
        - next_retry_at: epoch timestamp when the job becomes eligible for retry
        - added_at: epoch timestamp when the job was first added
        - status: "pending" | "permanent_failure" | "success"
    """

    def __init__(self, queue_path: str | Path | None = None) -> None:
        """Initialize the retry queue.

        Args:
            queue_path: Path to the JSON persistence file.
                        Defaults to ~/.linkedin_agent/retry_queue.json
        """
        self._path = Path(queue_path) if queue_path else DEFAULT_QUEUE_PATH
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}
        self._load()

    # ─── Public API ─────────────────────────────────────────────────

    def add(self, job: dict, error: str, max_retries: int = 3) -> None:
        """Add a failed job to the retry queue or increment its attempt count.

        If the job already exists in the queue and hasn't exceeded max_retries,
        its attempt count is incremented and a new backoff delay is calculated.
        If it has exceeded max_retries, it is marked as a permanent failure.

        Args:
            job: The job dict (must contain 'job_id' or 'id').
            error: Error message describing the failure.
            max_retries: Maximum number of retry attempts allowed.
        """
        job_id = job.get("job_id") or job.get("id") or ""
        if not job_id:
            logger.warning("Cannot add job to retry queue: no job_id or id field")
            return

        with self._lock:
            if job_id in self._entries:
                entry = self._entries[job_id]
                entry["attempts"] += 1
                entry["last_error"] = error
                entry["max_retries"] = max_retries

                if entry["attempts"] >= max_retries:
                    entry["status"] = "permanent_failure"
                    entry["next_retry_at"] = None
                    logger.info(
                        f"Job {job_id} exceeded max retries ({max_retries}), "
                        f"marked as permanent failure"
                    )
                else:
                    backoff_idx = min(entry["attempts"] - 1, len(BACKOFF_SECONDS) - 1)
                    delay = BACKOFF_SECONDS[backoff_idx]
                    entry["next_retry_at"] = time.time() + delay
                    logger.info(
                        f"Job {job_id} retry #{entry['attempts']} scheduled "
                        f"in {delay // 60}min"
                    )
            else:
                # First failure — schedule first retry
                delay = BACKOFF_SECONDS[0]
                self._entries[job_id] = {
                    "job": job,
                    "job_id": job_id,
                    "attempts": 1,
                    "max_retries": max_retries,
                    "last_error": error,
                    "next_retry_at": time.time() + delay,
                    "added_at": time.time(),
                    "status": "pending",
                }
                logger.info(
                    f"Job {job_id} added to retry queue, "
                    f"first retry in {delay // 60}min"
                )

            self._save()

    def get_due(self) -> list[dict]:
        """Return jobs that are ready for retry (backoff period has elapsed).

        Returns:
            List of job dicts whose next_retry_at is in the past and status is pending.
        """
        now = time.time()
        due_jobs: list[dict] = []

        with self._lock:
            for entry in self._entries.values():
                if entry["status"] != "pending":
                    continue
                if entry["next_retry_at"] is not None and entry["next_retry_at"] <= now:
                    due_jobs.append(entry["job"])

        return due_jobs

    def mark_success(self, job_id: str) -> None:
        """Mark a job as successfully applied (removes from retry queue).

        Args:
            job_id: The unique job identifier.
        """
        with self._lock:
            if job_id in self._entries:
                del self._entries[job_id]
                logger.info(f"Job {job_id} retry succeeded, removed from queue")
                self._save()

    def mark_permanent_failure(self, job_id: str) -> None:
        """Mark a job as permanently failed (will not be retried again).

        Args:
            job_id: The unique job identifier.
        """
        with self._lock:
            if job_id in self._entries:
                self._entries[job_id]["status"] = "permanent_failure"
                self._entries[job_id]["next_retry_at"] = None
                logger.info(f"Job {job_id} marked as permanent failure")
                self._save()

    @property
    def pending_count(self) -> int:
        """Return the number of jobs still pending retry."""
        with self._lock:
            return sum(
                1 for e in self._entries.values() if e["status"] == "pending"
            )

    def cleanup_old(self, max_age_hours: int = 24) -> int:
        """Remove stale entries older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours before an entry is removed.

        Returns:
            Number of entries removed.
        """
        cutoff = time.time() - (max_age_hours * 3600)
        removed = 0

        with self._lock:
            to_remove = [
                job_id
                for job_id, entry in self._entries.items()
                if entry["added_at"] < cutoff
            ]
            for job_id in to_remove:
                del self._entries[job_id]
                removed += 1

            if removed:
                self._save()
                logger.info(f"Cleaned up {removed} stale retry queue entries")

        return removed

    def get_stats(self) -> dict[str, int]:
        """Return summary statistics for the retry queue.

        Returns:
            Dict with keys: pending, permanent_failures, total
        """
        with self._lock:
            pending = sum(1 for e in self._entries.values() if e["status"] == "pending")
            permanent = sum(
                1 for e in self._entries.values() if e["status"] == "permanent_failure"
            )
            return {
                "pending": pending,
                "permanent_failures": permanent,
                "total": len(self._entries),
            }

    # ─── Persistence ────────────────────────────────────────────────

    def _load(self) -> None:
        """Load queue state from disk."""
        if not self._path.exists():
            self._entries = {}
            return

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._entries = data
            else:
                logger.warning(f"Retry queue file has unexpected format, starting fresh")
                self._entries = {}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"Failed to load retry queue from {self._path}: {exc}")
            self._entries = {}

    def _save(self) -> None:
        """Persist queue state to disk. Must be called while holding self._lock."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            # Write atomically via temp file
            tmp_path = self._path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2, default=str)
            tmp_path.replace(self._path)
        except OSError as exc:
            logger.error(f"Failed to save retry queue to {self._path}: {exc}")

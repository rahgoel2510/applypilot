"""Cloud dedup database — Turso (LibSQL) backed, forever persistent.

Tracks every job the agent has ever seen across all machines.
Prevents duplicate scoring, applications, and InMail.

Usage:
    from linkedin_agent.dedup_db import get_dedup_db
    db = get_dedup_db()
    if db.is_seen("4441030628"):
        skip  # Already processed
    else:
        db.mark_seen("4441030628", title="...", company="...", status="discovered")
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

TURSO_URL = os.environ.get("TURSO_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "")


class DedupDB:
    """Cloud-backed dedup database using Turso (LibSQL).

    Stores every job_id ever seen. Shared across Mac/Windows/Docker.
    """

    def __init__(self):
        self._conn = None
        self._connected = False
        self._connect()

    def _connect(self):
        """Connect to Turso cloud DB."""
        if not TURSO_URL or not TURSO_TOKEN:
            logger.warning("TURSO_URL or TURSO_TOKEN not set. Dedup DB disabled.")
            self._connected = False
            return
        try:
            import libsql_experimental as libsql
            url = TURSO_URL
            token = TURSO_TOKEN

            self._conn = libsql.connect("applypilot_dedup.db", sync_url=url, auth_token=token)
            self._conn.sync()

            # Create table if not exists
            self._conn.execute('''CREATE TABLE IF NOT EXISTS jobs_seen (
                job_id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'discovered',
                match_score REAL,
                is_easy_apply INTEGER DEFAULT 0,
                reason TEXT
            )''')
            self._conn.commit()
            self._conn.sync()
            self._connected = True
            logger.info("Dedup DB connected (Turso cloud)")
        except ImportError:
            logger.warning("libsql_experimental not installed. Dedup DB disabled.")
            self._connected = False
        except Exception as e:
            logger.warning("Dedup DB connection failed: %s. Running without dedup.", e)
            self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def is_seen(self, job_id: str) -> bool:
        """Check if a job has been seen before."""
        if not self._connected:
            return False
        try:
            result = self._conn.execute(
                "SELECT status FROM jobs_seen WHERE job_id = ?", (job_id,)
            ).fetchone()
            return result is not None
        except Exception:
            return False

    def get_status(self, job_id: str) -> Optional[str]:
        """Get the current status of a previously seen job."""
        if not self._connected:
            return None
        try:
            result = self._conn.execute(
                "SELECT status FROM jobs_seen WHERE job_id = ?", (job_id,)
            ).fetchone()
            return result[0] if result else None
        except Exception:
            return None

    def mark_seen(
        self,
        job_id: str,
        title: str = "",
        company: str = "",
        location: str = "",
        status: str = "discovered",
        match_score: float = None,
        is_easy_apply: bool = False,
        reason: str = "",
    ) -> None:
        """Record a job as seen. Updates if already exists."""
        if not self._connected:
            return
        try:
            self._conn.execute('''
                INSERT INTO jobs_seen (job_id, title, company, location, status, match_score, is_easy_apply, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = CASE WHEN excluded.status > status THEN excluded.status ELSE status END,
                    match_score = COALESCE(excluded.match_score, match_score),
                    is_easy_apply = COALESCE(excluded.is_easy_apply, is_easy_apply),
                    reason = COALESCE(excluded.reason, reason)
            ''', (job_id, title, company, location, status, match_score, int(is_easy_apply), reason))
            self._conn.commit()
        except Exception as e:
            logger.debug("Dedup write failed: %s", e)

    def mark_applied(self, job_id: str) -> None:
        """Update a job's status to 'applied'."""
        self.mark_seen(job_id, status="applied")

    def mark_skipped(self, job_id: str, reason: str = "") -> None:
        """Update a job's status to 'skipped'."""
        self.mark_seen(job_id, status="skipped", reason=reason)

    def sync(self) -> None:
        """Sync local cache to cloud."""
        if self._connected:
            try:
                self._conn.sync()
            except Exception:
                pass

    def stats(self) -> dict:
        """Get counts by status."""
        if not self._connected:
            return {}
        try:
            result = self._conn.execute(
                "SELECT status, COUNT(*) FROM jobs_seen GROUP BY status"
            ).fetchall()
            return {row[0]: row[1] for row in result}
        except Exception:
            return {}

    def total_seen(self) -> int:
        """Total unique jobs ever seen."""
        if not self._connected:
            return 0
        try:
            result = self._conn.execute("SELECT COUNT(*) FROM jobs_seen").fetchone()
            return result[0] if result else 0
        except Exception:
            return 0


# Singleton
_dedup: Optional[DedupDB] = None


def get_dedup_db() -> DedupDB:
    global _dedup
    if _dedup is None:
        _dedup = DedupDB()
    return _dedup

"""Tracker integration — pushes agent events and activity logs to the Job Application Tracker API.

The tracker is a local Kanban board web app that records every action
the agent takes (applications submitted, drafts saved, jobs skipped)
and maintains a full activity trail of all agent operations.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TRACKER_URL = "http://127.0.0.1:8000/api"


class TrackerClient:
    """HTTP client that pushes job events and activity logs to the tracker backend.

    Usage:
        tracker = TrackerClient()
        await tracker.push_event(event="submitted", title="Engineer", company="Corp")
        await tracker.log("cycle_start", "info", "Scan cycle started — 50 jobs to process")
    """

    def __init__(self, base_url: str = DEFAULT_TRACKER_URL, timeout: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Job event webhook (creates job + log entry on backend)
    # ------------------------------------------------------------------

    async def push_event(
        self,
        event: Literal["discovered", "reached_out", "submitted", "paused", "skipped"],
        title: str,
        company: str,
        location: str | None = None,
        match_score: float | None = None,
        posting_url: str | None = None,
    ) -> bool:
        """Push a job event to the tracker webhook.

        This creates both a job card AND an activity log entry on the backend.
        """
        payload = {
            "event": event,
            "title": title,
            "company": company,
            "location": location,
            "match_score": match_score,
            "posting_url": posting_url,
        }
        return await self._post(f"{self._base_url}/webhook/agent", payload)

    # ------------------------------------------------------------------
    # Activity Log push (lifecycle, errors, tally, etc.)
    # ------------------------------------------------------------------

    async def log(
        self,
        event_type: str,
        severity: Literal["info", "success", "warning", "error"] = "info",
        message: str = "",
        title: str | None = None,
        company: str | None = None,
        stage: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Push an activity log entry to the tracker.

        Args:
            event_type: One of: agent_start, agent_stop, cycle_start, cycle_end,
                        job_submitted, job_paused, job_skipped, job_error,
                        inmail_drafted, inmail_sent, telegram_sent,
                        human_input_requested, human_input_received,
                        error, warning, info
            severity: info, success, warning, or error
            message: Human-readable description of the event.
            title: Job title (optional, for job-related events).
            company: Company name (optional, for job-related events).
            stage: Current stage (optional).
            metadata: Extra data dict to store as JSON (optional).

        Returns:
            True if log was pushed successfully.
        """
        payload = {
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "title": title,
            "company": company,
            "stage": stage,
            "metadata_json": json.dumps(metadata) if metadata else None,
        }
        return await self._post(f"{self._base_url}/logs", payload)

    # ------------------------------------------------------------------
    # Convenience lifecycle methods
    # ------------------------------------------------------------------

    async def log_agent_start(self, interval_minutes: int, active_hours: str) -> bool:
        """Log agent startup."""
        return await self.log(
            "agent_start",
            "success",
            f"Agent started — interval: {interval_minutes}m, active: {active_hours}",
            metadata={"interval_minutes": interval_minutes, "active_hours": active_hours},
        )

    async def log_agent_stop(self, reason: str = "shutdown") -> bool:
        """Log agent shutdown."""
        return await self.log(
            "agent_stop", "info", f"Agent stopped — {reason}",
            metadata={"reason": reason},
        )

    async def log_cycle_start(self, max_postings: int, collection: str) -> bool:
        """Log start of a scan cycle."""
        return await self.log(
            "cycle_start",
            "info",
            f"Scan cycle started — up to {max_postings} jobs from '{collection}'",
            metadata={"max_postings": max_postings, "collection": collection},
        )

    async def log_cycle_end(
        self, submitted: int, skipped: int, paused: int, errors: int, duration_sec: int
    ) -> bool:
        """Log end of a scan cycle with tally."""
        total = submitted + skipped + paused + errors
        return await self.log(
            "cycle_end",
            "success" if errors == 0 else "warning",
            f"Cycle complete — {submitted} applied, {skipped} skipped, "
            f"{paused} paused, {errors} errors ({total} total in {duration_sec}s)",
            metadata={
                "submitted": submitted,
                "skipped": skipped,
                "paused": paused,
                "errors": errors,
                "total": total,
                "duration_sec": duration_sec,
            },
        )

    async def log_job_error(self, title: str, company: str, error: str) -> bool:
        """Log a job processing error."""
        return await self.log(
            "job_error", "error", f"Error: {error}",
            title=title, company=company,
            metadata={"error": error},
        )

    async def log_inmail_drafted(self, title: str, company: str, recruiter: str) -> bool:
        """Log InMail draft generation."""
        return await self.log(
            "inmail_drafted", "info",
            f"InMail drafted to {recruiter}",
            title=title, company=company,
            metadata={"recruiter": recruiter},
        )

    async def log_telegram_sent(self, message_type: str) -> bool:
        """Log Telegram notification sent."""
        return await self.log(
            "telegram_sent", "info", f"Telegram: {message_type} sent",
            metadata={"message_type": message_type},
        )

    async def log_human_input_requested(self, title: str, company: str, fields: list[str]) -> bool:
        """Log that human input was requested for a paused job."""
        return await self.log(
            "human_input_requested", "warning",
            f"Waiting for human input: {', '.join(fields)}",
            title=title, company=company,
            metadata={"blocking_fields": fields},
        )

    # ------------------------------------------------------------------
    # InMail Draft persistence
    # ------------------------------------------------------------------

    async def push_inmail_draft(
        self,
        job_title: str,
        company: str,
        recruiter: str,
        draft_text: str,
        job_id: str | None = None,
    ) -> bool:
        """Push an InMail draft to the tracker database.

        Args:
            job_title: Title of the job this InMail is for.
            company: Company name.
            recruiter: Recruiter/hiring manager name.
            draft_text: The generated InMail message text.
            job_id: Optional job ID to link the draft to a tracked job.

        Returns:
            True if the draft was stored successfully.
        """
        payload = {
            "job_title": job_title,
            "company": company,
            "recruiter_name": recruiter,
            "draft_text": draft_text,
            "job_id": job_id,
            "status": "drafted",
        }
        return await self._post(f"{self._base_url}/inmail-drafts", payload)

    # ------------------------------------------------------------------
    # Internal HTTP helper
    # ------------------------------------------------------------------

    async def _post(self, url: str, payload: dict) -> bool:
        """Fire-and-forget POST. Returns True on success, False otherwise."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)

            if response.status_code in (200, 201):
                logger.debug("Tracker POST %s → %d", url, response.status_code)
                return True
            else:
                logger.warning(
                    "Tracker returned %d for %s: %s",
                    response.status_code, url, response.text[:200],
                )
                return False

        except httpx.ConnectError:
            logger.debug("Tracker not available at %s", url)
            return False
        except httpx.TimeoutException:
            logger.debug("Tracker request timed out: %s", url)
            return False
        except Exception as exc:
            logger.debug("Tracker push failed: %s", exc)
            return False


# Module-level singleton
_tracker: TrackerClient | None = None


def get_tracker(base_url: str = DEFAULT_TRACKER_URL) -> TrackerClient:
    """Return a module-level TrackerClient singleton."""
    global _tracker
    if _tracker is None:
        _tracker = TrackerClient(base_url=base_url)
    return _tracker

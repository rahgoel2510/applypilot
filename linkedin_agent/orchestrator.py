"""Main orchestrator that ties all modules together."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from linkedin_agent.config import Settings, get_config
from linkedin_agent.browser import LinkedInBrowser as BrowserManager
from linkedin_agent.matcher import JobMatcher
from linkedin_agent.applicant import ApplicationExecutor, ApplicationResult
from linkedin_agent.telegram_bot import TelegramNotifier
from linkedin_agent.inmail import InMailDrafter
from linkedin_agent.tracker_client import get_tracker
from linkedin_agent.logger import setup_logging


class JobStatus(str, Enum):
    """Possible outcomes for a job processing attempt."""

    SUBMITTED = "submitted"
    SKIPPED = "skipped"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class CycleTally:
    """Running counts for the current scan cycle."""

    submitted: int = 0
    skipped: int = 0
    paused: int = 0
    errors: int = 0
    total: int = 0
    started_at: datetime = field(default_factory=datetime.now)

    def record(self, status: JobStatus) -> None:
        self.total += 1
        if status == JobStatus.SUBMITTED:
            self.submitted += 1
        elif status == JobStatus.SKIPPED:
            self.skipped += 1
        elif status == JobStatus.PAUSED:
            self.paused += 1
        elif status == JobStatus.ERROR:
            self.errors += 1

    def summary(self) -> str:
        elapsed = datetime.now() - self.started_at
        minutes = int(elapsed.total_seconds() // 60)
        return (
            f"📊 *Scan Cycle Report*\n"
            f"─────────────────\n"
            f"✅ Submitted: {self.submitted}\n"
            f"⏭️ Skipped: {self.skipped}\n"
            f"⏸️ Paused: {self.paused}\n"
            f"❌ Errors: {self.errors}\n"
            f"─────────────────\n"
            f"Total: {self.total} jobs in {minutes}m"
        )


class JobAgent:
    """Main agent that orchestrates the full job-application pipeline.

    Ties together browser automation, job matching, application submission,
    InMail drafting, Telegram notifications, and scheduling.
    """

    def __init__(self, config: Settings | None = None, dry_run: bool = False) -> None:
        """Initialize the agent with config and all sub-modules.

        Args:
            config: Pre-loaded Settings instance. If None, loads via get_config().
            dry_run: If True, scan and score jobs but do NOT submit applications.
        """
        self.config = config or get_config(validate=True)
        self.dry_run = dry_run
        self.log = setup_logging(level="INFO")

        # Initialize modules
        self.browser = BrowserManager()
        self.matcher = JobMatcher(threshold=self.config.job_search.match_threshold)
        self.notifier = TelegramNotifier(
            bot_token=self.config.telegram.bot_token,
            chat_id=self.config.telegram.chat_id,
        )
        self.inmail = InMailDrafter(self.config)
        self.tracker = get_tracker()

        # ApplicationExecutor requires browser + matcher + notifier (created per cycle)
        self._applicant: ApplicationExecutor | None = None

        # State
        self.tally = CycleTally()
        self._shutdown_event = asyncio.Event()

    # ─── Core Pipeline ──────────────────────────────────────────────

    async def process_job(self, job: dict[str, Any]) -> ApplicationResult:
        """Process a single job through the full pipeline.

        Steps:
        1. Score relevance via matcher
        2. If below threshold, skip
        3. If above threshold, attempt application via ApplicationExecutor
           (unless dry_run is True, in which case log the decision only)
        4. Return result (submitted / paused / skipped / error)
        """
        job_title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        self.log.info(f"Processing: {job_title} @ {company}")

        # Check for external apply
        if self.config.job_search.skip_external_apply:
            if job.get("is_external", False):
                self.log.info(f"Skipping external apply: {job_title} @ {company}")
                return ApplicationResult(
                    status="skipped_external",
                    job_id=job.get("id", "unknown"),
                    title=job_title,
                    company=company,
                    location=job.get("location", "Unknown"),
                )

        # Check deduplication
        if self.matcher.is_duplicate(company, job_title):
            self.log.info(f"Skipping duplicate: {job_title} @ {company}")
            return ApplicationResult(
                status="duplicate",
                job_id=job.get("id", "unknown"),
                title=job_title,
                company=company,
                location=job.get("location", "Unknown"),
            )

        # Dry-run mode: report what WOULD happen, don't apply
        if self.dry_run:
            match_score = job.get("match_score")
            if match_score is not None and not self.matcher.meets_threshold(match_score):
                self.log.info(
                    f"[DRY RUN] Would SKIP (score {match_score:.0%}): {job_title} @ {company}"
                )
                return ApplicationResult(
                    status="skipped_threshold",
                    job_id=job.get("id", "unknown"),
                    title=job_title,
                    company=company,
                    location=job.get("location", "Unknown"),
                    match_score=match_score,
                )
            else:
                self.log.info(
                    f"[DRY RUN] Would APPLY (score {match_score}): {job_title} @ {company}"
                )
                return ApplicationResult(
                    status="submitted",
                    job_id=job.get("id", "unknown"),
                    title=job_title,
                    company=company,
                    location=job.get("location", "Unknown"),
                    match_score=match_score,
                )

        # Submit application via executor
        if self._applicant is None:
            raise RuntimeError("ApplicationExecutor not initialized — call run_scan_cycle first")

        result = await self._applicant.apply_to_job(job)

        # Track dedup on success
        if result.status == "submitted":
            self.matcher.add_to_applied(company, job_title)

        return result

    async def send_inmail_for_job(self, job: dict[str, Any]) -> None:
        """Draft InMail for the recruiter and send to Telegram for review."""
        try:
            recruiter = job.get("recruiter", "the hiring manager")
            candidate_summary = self.inmail.get_candidate_summary()

            draft = await self.inmail.draft_inmail(
                job_title=job.get("title", "N/A"),
                company=job.get("company", "N/A"),
                recruiter_name=recruiter,
                job_description=job.get("description", ""),
                candidate_summary=candidate_summary,
            )

            await self.notifier.send_inmail_draft(
                job_title=job.get("title", "N/A"),
                company=job.get("company", "N/A"),
                recruiter=recruiter,
                draft=draft,
            )

            await self.tracker.log_inmail_drafted(
                title=job.get("title", "N/A"),
                company=job.get("company", "N/A"),
                recruiter=recruiter,
            )
        except Exception as exc:
            self.log.warning(f"Failed to draft InMail: {exc}")

    async def report_tally(self) -> None:
        """Send the current cycle tally to Telegram."""
        tally_dict = {
            "submitted": self.tally.submitted,
            "paused": self.tally.paused,
            "skipped_threshold": self.tally.skipped,
            "skipped_external": 0,
        }
        await self.notifier.send_tally_report(tally_dict)

    # ─── Scan Cycle ─────────────────────────────────────────────────

    async def run_scan_cycle(self) -> None:
        """Execute one full scan cycle.

        Flow:
        a. Notify Telegram: 'Starting scan cycle'
        b. Launch browser
        c. Navigate to job collection
        d. Get job listings
        e. Process each job
        f. Send tally report
        g. Close browser
        """
        self.tally = CycleTally()
        collection = self.config.job_search.collection
        max_postings = self.config.job_search.max_postings_per_run
        inmail_enabled = self.config.inmail.enabled
        notify_on_submit = self.config.telegram.notify_on_submit
        notify_on_pause = self.config.telegram.notify_on_pause

        # a. Notify start
        await self.notifier.send_notification("🚀 Starting scan cycle...")
        await self.tracker.log_cycle_start(max_postings, collection)
        self.log.info("Scan cycle started")

        try:
            # b. Launch browser
            await self.browser.launch()

            # Login if needed (uses persistent session — only enters creds first time)
            await self.browser.login(
                email=self.config.linkedin_email,
                password=self.config.linkedin_password,
            )

            # Initialize the application executor for this cycle
            self._applicant = ApplicationExecutor(
                browser=self.browser,
                matcher=self.matcher,
                notifier=self.notifier,
                config={
                    "candidate": {
                        "name": self.config.candidate.name,
                        "email": self.config.candidate.email,
                        "phone": self.config.candidate.phone,
                        "resume_filename": self.config.candidate.resume_filename,
                        "notice_period": self.config.candidate.notice_period,
                        "willing_to_relocate": self.config.candidate.willing_to_relocate,
                        "work_authorization": self.config.candidate.work_authorization,
                        "preferred_cities": list(self.config.candidate.preferred_cities),
                    },
                    "job_search": {
                        "match_threshold": self.config.job_search.match_threshold,
                        "skip_external_apply": self.config.job_search.skip_external_apply,
                    },
                    "telegram": {
                        "notify_on_submit": notify_on_submit,
                        "notify_on_pause": notify_on_pause,
                    },
                },
            )

            # c. Navigate to job collection
            await self.browser.navigate_to_jobs(collection=collection)

            # d. Get job listings
            jobs = await self.browser.get_job_listings(max_count=max_postings)
            self.log.info(f"Found {len(jobs)} job(s) to process")

            # e. Process each job
            for job in jobs:
                if self._shutdown_event.is_set():
                    self.log.info("Shutdown requested, stopping cycle")
                    break

                try:
                    result = await self.process_job(job)
                    status = self._map_result_status(result.status)
                    self.tally.record(status)

                    # Post-submission actions
                    if status == JobStatus.SUBMITTED:
                        if inmail_enabled:
                            await self.send_inmail_for_job(job)

                    elif status == JobStatus.PAUSED:
                        if notify_on_pause:
                            blocking = result.blocking_fields or []
                            fields_str = ", ".join(blocking) if blocking else "unknown"

                            # Ask for human input
                            response = await self.notifier.ask_human_input(
                                job_title=job.get("title", "Unknown"),
                                company=job.get("company", "Unknown"),
                                fields=blocking,
                                timeout=300,
                            )

                            if response.upper() == "SKIP":
                                self.log.info("Human chose to skip paused job")
                            elif response:
                                self.log.info("Human provided input — retrying")
                                retry_result = await self._applicant.apply_to_job(job)
                                if retry_result.status == "submitted":
                                    self.tally.paused -= 1
                                    self.tally.submitted += 1

                    # Log result
                    self.log.info(
                        f"Result: {result.status} — "
                        f"{job.get('title')} @ {job.get('company')}"
                    )

                    # Push to tracker (fire-and-forget, never blocks pipeline)
                    tracker_event = {
                        "submitted": "submitted",
                        "paused": "paused",
                        "skipped_threshold": "skipped",
                        "skipped_external": "skipped",
                        "duplicate": "skipped",
                    }.get(result.status)
                    if tracker_event:
                        await self.tracker.push_event(
                            event=tracker_event,
                            title=job.get("title", "Unknown"),
                            company=job.get("company", "Unknown"),
                            location=job.get("location"),
                            match_score=getattr(result, "match_score", None),
                            posting_url=job.get("posting_url"),
                        )

                except Exception as job_exc:
                    self.tally.record(JobStatus.ERROR)
                    self.log.error(
                        f"Error processing {job.get('title', '?')}: {job_exc}",
                        exc_info=True,
                    )
                    await self.tracker.log_job_error(
                        title=job.get("title", "Unknown"),
                        company=job.get("company", "Unknown"),
                        error=str(job_exc),
                    )
                    await self.notifier.send_notification(
                        f"❌ Error on {job.get('title', '?')} @ "
                        f"{job.get('company', '?')}: {job_exc}"
                    )

        except Exception as cycle_exc:
            self.log.error(f"Scan cycle error: {cycle_exc}", exc_info=True)
            await self.tracker.log(
                "error", "error", f"Scan cycle failed: {cycle_exc}",
                metadata={"traceback": str(cycle_exc)},
            )
            await self.notifier.send_notification(
                f"🚨 Scan cycle failed: {cycle_exc}"
            )

        finally:
            # f. Send tally report
            await self.report_tally()

            # Log cycle completion
            elapsed = (datetime.now() - self.tally.started_at).total_seconds()
            await self.tracker.log_cycle_end(
                submitted=self.tally.submitted,
                skipped=self.tally.skipped,
                paused=self.tally.paused,
                errors=self.tally.errors,
                duration_sec=int(elapsed),
            )

            # g. Close browser
            try:
                await self.browser.close()
            except Exception as close_exc:
                self.log.warning(f"Browser close error: {close_exc}")

        self.log.info("Scan cycle complete")

    # ─── Run Modes ──────────────────────────────────────────────────

    async def run_once(self) -> None:
        """Run a single scan cycle with proper startup and shutdown."""
        self.log.info("Running single scan cycle")
        try:
            await self.run_scan_cycle()
        finally:
            await self.shutdown()

    async def run_daemon(self) -> None:
        """Run continuously on a schedule until shutdown is requested."""
        self.log.info("Starting daemon mode")
        interval = self.config.scheduler.interval_minutes
        active_start = self.config.scheduler.active_hours_start
        active_end = self.config.scheduler.active_hours_end

        await self.notifier.send_notification(
            f"🤖 Daemon started — Interval: {interval}m | "
            f"Active hours: {active_start}:00–{active_end}:00"
        )
        await self.tracker.log_agent_start(
            interval_minutes=interval,
            active_hours=f"{active_start}:00–{active_end}:00",
        )

        try:
            while not self._shutdown_event.is_set():
                now = datetime.now()
                current_hour = now.hour

                if active_start <= current_hour < active_end:
                    await self.run_scan_cycle()
                else:
                    self.log.info(
                        f"Outside active hours ({active_start}–{active_end}), "
                        f"sleeping until next check"
                    )

                # Wait for next interval or shutdown
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=interval * 60,
                    )
                    # If we get here, shutdown was requested
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, run next cycle
                    continue

        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Clean up all resources."""
        self.log.info("Shutting down...")
        self._shutdown_event.set()

        try:
            await self.tracker.log_agent_stop(reason="shutdown requested")
        except Exception:
            pass

        try:
            await self.browser.close()
        except Exception:
            pass

        try:
            await self.notifier.send_notification("👋 Agent shutting down")
        except Exception:
            pass

        self.log.info("Shutdown complete")

    def request_shutdown(self) -> None:
        """Signal the agent to stop (called from signal handlers)."""
        self._shutdown_event.set()

    # ─── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _map_result_status(status: str) -> JobStatus:
        """Map ApplicationResult.status string to our JobStatus enum."""
        mapping = {
            "submitted": JobStatus.SUBMITTED,
            "paused": JobStatus.PAUSED,
            "skipped_threshold": JobStatus.SKIPPED,
            "skipped_external": JobStatus.SKIPPED,
            "duplicate": JobStatus.SKIPPED,
            "error": JobStatus.ERROR,
        }
        return mapping.get(status, JobStatus.ERROR)


def main() -> None:
    """Entry point called from __main__.py — delegates to CLI."""
    from linkedin_agent.__main__ import cli

    cli()

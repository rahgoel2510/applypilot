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

            # c. Search jobs by keywords (not just browse Recommended)
            keywords = self.config.job_search.keywords
            locations = self.config.job_search.locations
            posted_within = self.config.job_search.posted_within
            all_jobs: list[dict] = []

            # Search each keyword + location combo
            for keyword in keywords:
                if self._shutdown_event.is_set():
                    break
                if len(all_jobs) >= max_postings:
                    break

                location = locations[0] if locations else ""
                self.log.info(f"Searching: '{keyword}' in '{location}'")

                await self.browser.search_jobs(
                    keyword=keyword,
                    location=location,
                    posted_within=posted_within,
                )

                # Get job listings from search results
                remaining = max_postings - len(all_jobs)
                page_jobs = await self.browser.get_job_listings(max_count=min(remaining, 25))
                all_jobs.extend(page_jobs)
                self.log.info(f"  Found {len(page_jobs)} jobs for '{keyword}' (total: {len(all_jobs)})")

            self.log.info(f"Total jobs to evaluate: {len(all_jobs)}")

            # d. Process each job: open → score → decide → apply/skip
            for job in all_jobs:
                if self._shutdown_event.is_set():
                    self.log.info("Shutdown requested, stopping cycle")
                    break

                try:
                    job_title = job.get("title", "Unknown")
                    company = job.get("company", "Unknown")
                    job_id = job.get("job_id", "")

                    self.log.info(f"Evaluating: {job_title} @ {company}")

                    # Skip duplicates early
                    if self.matcher.is_duplicate(company, job_title):
                        self.log.info(f"  → Skipping (duplicate)")
                        self.tally.record(JobStatus.SKIPPED)
                        continue

                    # Open the job page to check match score
                    if job_id:
                        await self.browser.open_job(job_id)
                    else:
                        self.log.warning(f"  → No job ID, skipping")
                        self.tally.record(JobStatus.SKIPPED)
                        continue

                    # Check if external apply
                    if self.config.job_search.skip_external_apply:
                        is_external = await self.browser.is_external_apply()
                        if is_external:
                            self.log.info(f"  → Skipping (external apply)")
                            self.tally.record(JobStatus.SKIPPED)
                            await self.tracker.push_event(
                                event="skipped", title=job_title, company=company,
                                location=job.get("location"), posting_url=job.get("url"),
                            )
                            continue

                    # Get match score from "Show match details"
                    matched, total = await self.browser.get_match_score()
                    if total > 0:
                        score = matched / total
                        job["match_score"] = score
                        self.log.info(f"  → Match: {matched}/{total} ({score:.0%})")
                    else:
                        score = None
                        self.log.info(f"  → No match data available (applying anyway)")

                    # Apply threshold
                    if score is not None and not self.matcher.meets_threshold(score):
                        self.log.info(f"  → Skipping (below {self.config.job_search.match_threshold:.0%} threshold)")
                        self.tally.record(JobStatus.SKIPPED)
                        await self.tracker.push_event(
                            event="skipped", title=job_title, company=company,
                            location=job.get("location"), match_score=score,
                            posting_url=job.get("url"),
                        )
                        continue

                    # Passed threshold — mark as DISCOVERED in tracker
                    self.log.info(f"  ✓ Match! Adding to tracker as 'discovered'")
                    await self.tracker.push_event(
                        event="discovered", title=job_title, company=company,
                        location=job.get("location"), match_score=score,
                        posting_url=job.get("url"),
                    )

                    # Apply (or dry-run log)
                    if self.dry_run:
                        self.log.info(f"  ✓ [DRY RUN] Would APPLY (score: {score:.0%})")
                        self.tally.record(JobStatus.SUBMITTED)
                    else:
                        # Actually apply — will update discovered→applied in tracker
                        job["match_score"] = score
                        job["id"] = job_id
                        result = await self._applicant.apply_to_job(job)
                        status = self._map_result_status(result.status)
                        self.tally.record(status)

                        if result.status == "submitted":
                            self.matcher.add_to_applied(company, job_title)
                            # Update tracker: discovered → applied
                            await self.tracker.push_event(
                                event="submitted", title=job_title, company=company,
                                location=job.get("location"), match_score=score,
                                posting_url=job.get("url"),
                            )
                            if inmail_enabled:
                                await self.send_inmail_for_job(job)
                        elif result.status == "paused":
                            await self.tracker.push_event(
                                event="paused", title=job_title, company=company,
                                location=job.get("location"), match_score=score,
                                posting_url=job.get("url"),
                            )

                    # Log result
                    self.log.info(f"  Done: {job_title} @ {company}")

                except Exception as job_exc:
                    self.tally.record(JobStatus.ERROR)
                    self.log.error(
                        f"Error processing {job.get('title', '?')}: {job_exc}",
                        exc_info=True,
                    )
                    await self.tracker.log_job_error(
                        title=job.get("title", "Unknown"),
                        company=job.get("company", "Unknown"),
                        error=str(job_exc)[:200],
                    )
                    safe_error = str(job_exc)[:100].replace('<', '').replace('>', '')
                    await self.notifier.send_notification(
                        f"❌ Error on {job.get('title', '?')} @ "
                        f"{job.get('company', '?')}: {safe_error}"
                    )

        except Exception as cycle_exc:
            self.log.error(f"Scan cycle error: {cycle_exc}", exc_info=True)
            # Sanitize error message for Telegram (strip HTML-like content)
            safe_error = str(cycle_exc)[:200].replace('<', '').replace('>', '').replace('&', '')
            await self.tracker.log(
                "error", "error", f"Scan cycle failed: {safe_error}",
                metadata={"traceback": str(cycle_exc)[:500]},
            )
            await self.notifier.send_notification(
                f"🚨 Scan cycle failed: {safe_error}"
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

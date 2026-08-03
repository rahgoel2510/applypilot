"""Main orchestrator that ties all modules together.

Uses the DI container for all service dependencies, making the agent
fully testable with mockable services. Coordinates the scan pipeline:
discover → evaluate → apply → notify.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from linkedin_agent.config import Settings, get_config
from linkedin_agent.container import Container
from linkedin_agent.logger import setup_logging
from linkedin_agent.applicant import ApplicationResult
from linkedin_agent.resilience import CircuitBreaker, retry_with_backoff, graceful_fallback


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

    Uses dependency injection via Container for all services, enabling:
    - Easy testing (swap any service with a mock)
    - Loose coupling (services interact via protocols)
    - Resilience (circuit breakers on external services)
    """

    def __init__(
        self,
        config: Settings | None = None,
        dry_run: bool = False,
        container: Container | None = None,
    ) -> None:
        """Initialize the agent with config and DI container.

        Args:
            config: Pre-loaded Settings instance. If None, loads via get_config().
            dry_run: If True, scan and score jobs but do NOT submit applications.
            container: Optional pre-configured DI container (for testing).
        """
        self.config = config or get_config(validate=True)
        self.dry_run = dry_run
        self.log = setup_logging(level="INFO")

        # DI Container — all services resolved through here
        self._container = container or Container(self.config)

        # Resolve services from container
        self.browser = self._container.browser
        self.matcher = self._container.scorer
        self.notifier = self._container.notifier
        self.inmail = self._container.inmail
        self.tracker = self._container.tracker

        # ApplicationExecutor requires browser + matcher + notifier (created per cycle)
        self._applicant = None

        # Retry queue for failed applications (persists across restarts)
        self.retry_queue = self._container.retry_queue

        # Daily application cap tracking (avoids LinkedIn rate limiting)
        self.daily_cap = self._container.daily_cap

        # Circuit breakers for external services
        self._telegram_cb = CircuitBreaker("telegram", failure_threshold=3, recovery_timeout=120)
        self._tracker_cb = CircuitBreaker("tracker", failure_threshold=5, recovery_timeout=60)

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

            # Persist InMail draft to the tracker database
            await self.tracker.push_inmail_draft(
                job_title=job.get("title", "N/A"),
                company=job.get("company", "N/A"),
                recruiter=recruiter,
                draft_text=draft,
                job_id=job.get("job_id") or job.get("id"),
            )

            await self.tracker.log_inmail_drafted(
                title=job.get("title", "N/A"),
                company=job.get("company", "N/A"),
                recruiter=recruiter,
            )
        except Exception as exc:
            self.log.warning(f"Failed to draft InMail: {exc}")

    async def report_tally(self, full_metrics: dict = None) -> None:
        """Send the current cycle tally to Telegram.

        Args:
            full_metrics: If provided, sends an enhanced tally with the full funnel
                breakdown. If None, falls back to the legacy 4-bucket format for
                backwards compatibility.
        """
        if full_metrics is not None:
            # Enhanced format with full funnel visibility
            total_found = full_metrics.get("total_found", 0)
            dedup_skipped = full_metrics.get("dedup_skipped", 0)
            new_discovered = full_metrics.get("new_discovered", 0)
            applied = full_metrics.get("applied", 0)
            external_manual = full_metrics.get("external_manual", 0)
            skipped_low_score = full_metrics.get("skipped_low_score", 0)
            paused = full_metrics.get("paused", 0)
            errors = full_metrics.get("errors", 0)

            enhanced_tally = {
                "submitted": applied,
                "paused": paused,
                "skipped_threshold": skipped_low_score,
                "skipped_external": external_manual,
                "total_found": total_found,
                "dedup_skipped": dedup_skipped,
                "new_discovered": new_discovered,
                "errors": errors,
            }
            await self.notifier.send_tally_report(enhanced_tally)
        else:
            # Legacy 4-bucket format (backwards compat)
            tally_dict = {
                "submitted": self.tally.submitted,
                "paused": self.tally.paused,
                "skipped_threshold": self.tally.skipped,
                "skipped_external": 0,
            }
            await self.notifier.send_tally_report(tally_dict)

    async def check_response_statuses(self) -> None:
        """Check LinkedIn for application response updates and sync to tracker."""
        self.log.info('Checking application response statuses...')
        try:
            statuses = await self.browser.check_application_statuses(max_check=30)
            updated = 0
            for item in statuses:
                status = item.get('status', '')
                # Map LinkedIn status text to our pipeline stages
                if 'viewed' in status or 'downloaded' in status:
                    stage = 'in_review'
                elif 'no longer' in status or 'closed' in status:
                    stage = 'rejected'
                else:
                    continue  # 'submitted' is default, no update needed

                await self.tracker.push_event(
                    event=stage,
                    title=item.get('title', ''),
                    company=item.get('company', ''),
                    posting_url=f"https://www.linkedin.com/jobs/view/{item['job_id']}/" if item.get('job_id') else None,
                )
                updated += 1

            if updated:
                self.log.info(f'  Updated {updated} application statuses')
                await self.notifier.send_notification(
                    f"📋 Status update: {updated} application(s) have new responses on LinkedIn"
                )
        except Exception as exc:
            self.log.warning(f'Could not check application statuses: {exc}')

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

        # Log active search mode
        active_mode = self.config.job_search.search_mode
        if active_mode and active_mode != 'custom':
            self.log.info(f'Search mode: {active_mode.upper()}')

        # Check daily application cap
        if self.daily_cap.is_at_limit:
            self.log.warning(
                f"Daily application cap reached ({self.daily_cap.today_count}/{self.daily_cap.daily_limit}). "
                f"Skipping this cycle to avoid LinkedIn rate limiting."
            )
            await self.notifier.send_notification(
                f"⚠️ Daily cap reached ({self.daily_cap.today_count}/{self.daily_cap.daily_limit}).\n"
                f"Pausing applications until tomorrow to protect your account."
            )
            return

        collection = self.config.job_search.collection
        max_postings = self.config.job_search.max_postings_per_run
        inmail_enabled = self.config.inmail.enabled
        notify_on_submit = self.config.telegram.notify_on_submit
        notify_on_pause = self.config.telegram.notify_on_pause

        # Check urgent mode
        urgent = self.config.scheduler.urgent_mode
        if urgent:
            # Check if urgent mode has expired
            from pathlib import Path as _UPath
            urgent_marker = _UPath.home() / '.linkedin_agent' / '.urgent_start'
            if not urgent_marker.exists():
                urgent_marker.parent.mkdir(parents=True, exist_ok=True)
                urgent_marker.write_text(datetime.now().isoformat())
            else:
                start_str = urgent_marker.read_text().strip()
                try:
                    start_date = datetime.fromisoformat(start_str)
                    days_elapsed = (datetime.now() - start_date).days
                    if days_elapsed >= self.config.scheduler.urgent_duration_days:
                        urgent = False
                        self.log.info(f'Urgent mode expired after {days_elapsed} days')
                except ValueError:
                    pass

            if urgent:
                max_postings = self.config.scheduler.urgent_max_postings
                self.log.info(f'URGENT MODE: max_postings={max_postings}')

        # Initialize counters for the finally block (may not reach assignment in try)
        total_jobs = 0
        dedup_skipped = 0
        discovered_count = 0
        applied_count = 0
        external_count = 0
        skipped_count = 0

        # a. Notify start (log only, no Telegram spam)
        await self.tracker.log_cycle_start(max_postings, collection)
        self.log.info("Pipeline started")

        try:
            # Pre-flight: validate AI model is configured and responsive
            import os
            ai_key = os.environ.get("OPENAI_API_KEY", "")
            ai_model = os.environ.get("AI_MODEL", "openrouter/free")
            if ai_key and not ai_key.startswith("placeholder"):
                self.log.info(f"AI model: {ai_model} ✓")
            else:
                self.log.info("AI model: not configured (LLM features disabled)")

            # b. Launch browser + session check
            import time as _time
            t0 = _time.time()
            self.log.info("Launching browser...")
            await self.browser.launch()
            self.log.info(f"Browser ready ({_time.time()-t0:.1f}s)")

            t1 = _time.time()
            self.log.info("Checking LinkedIn session...")
            await self.browser.login(
                email=self.config.linkedin_email,
                password=self.config.linkedin_password,
            )
            self.log.info(f"LinkedIn connected ✓ ({_time.time()-t1:.1f}s)")

            # Initialize the application executor for this cycle (via container)
            self._applicant = self._container.create_applicant(
                browser=self.browser,
                scorer=self.matcher,
                notifier=self.notifier,
            )

            # c. Determine if this is the first-ever run
            from pathlib import Path as _Path
            marker_file = _Path.home() / ".linkedin_agent" / ".first_run_complete"
            is_first_run = not marker_file.exists()

            # Also check dedup DB — if we've seen jobs before, it's not the first run
            if is_first_run:
                from linkedin_agent.dedup_db import get_dedup_db as _get_dedup_early
                _dedup_check = _get_dedup_early()
                if _dedup_check.connected and _dedup_check.total_seen() > 0:
                    is_first_run = False

            keywords = self.config.job_search.keywords
            custom_urls = self.config.job_search.custom_urls
            locations = self.config.job_search.locations

            if is_first_run:
                posted_within = self.config.job_search.initial_scan_window
                self.log.info(
                    f"First run detected — scanning past {posted_within} for initial pipeline"
                )
            else:
                posted_within = self.config.job_search.posted_within

            all_jobs: list[dict] = []
            seen_job_ids: set[str] = set()

            self.log.info(f"LinkedIn scanning started")
            await self.tracker.log("info", "info", "LinkedIn scanning started — searching across keywords and locations")

            # Source 1: Recommended jobs (LinkedIn's best matches for your profile)
            self.log.info("Checking Recommended jobs...")
            try:
                await self.browser.navigate_to_jobs(collection=collection)
                remaining = max_postings
                rec_jobs = await self.browser.get_job_listings(max_count=min(remaining, 15))
                for j in rec_jobs:
                    jid = j.get("job_id", "")
                    if jid and jid not in seen_job_ids:
                        all_jobs.append(j)
                        seen_job_ids.add(jid)
                if rec_jobs:
                    self.log.info(f"  Recommended → {len(rec_jobs)} jobs")
                else:
                    self.log.info(f"  Recommended → 0 jobs (may not be available in headless)")
            except Exception as rec_exc:
                self.log.info(f"  Recommended → skipped ({str(rec_exc)[:40]})")

            # Source 2: Keyword search across ALL locations
            if len(all_jobs) < max_postings:
                self.log.info(f"Searching by keywords: {keywords}")
                self.log.info(f"Across locations: {locations}")
                search_count = 0

                # Phase 1: Combined OR search for each location (most efficient)
                if len(keywords) > 1:
                    combined_query = " OR ".join(f'"{k}"' for k in keywords)
                    for location in locations:
                        if self._shutdown_event.is_set() or len(all_jobs) >= max_postings:
                            break
                        try:
                            await self.browser.search_jobs(
                                keyword=combined_query,
                                location=location,
                                posted_within=posted_within,
                            )
                            search_count += 1
                            remaining = max_postings - len(all_jobs)
                            page_jobs = await self.browser.get_job_listings(max_count=min(remaining, 25))
                            new_count = 0
                            for j in page_jobs:
                                jid = j.get("job_id", "")
                                if jid and jid not in seen_job_ids:
                                    all_jobs.append(j)
                                    seen_job_ids.add(jid)
                                    new_count += 1
                            self.log.info(f"  Combined search ({location}) → {new_count} jobs")
                        except Exception as search_err:
                            self.log.warning(f"  Combined search ({location}) → failed: {str(search_err)[:60]}. Continuing...")
                            await asyncio.sleep(3)

                # Phase 2: Individual keyword × location (only if OR search didn't find enough)
                or_found_count = len(all_jobs)
                if len(all_jobs) >= max_postings:
                    self.log.info(f'OR search already found {or_found_count} jobs (>= max {max_postings}) — skipping individual searches')
                elif or_found_count >= int(max_postings * 0.8):
                    self.log.info(f'OR search already found {or_found_count} jobs (>= 80% of {max_postings}) — skipping individual searches')
                else:
                    self.log.info(f'OR search found {or_found_count}/{max_postings} — running individual searches...')
                    or_phase_seen_ids = set(seen_job_ids)  # Snapshot of IDs found during OR phase
                    for keyword in keywords:
                        if self._shutdown_event.is_set() or len(all_jobs) >= max_postings:
                            break
                        for location in locations:
                            if self._shutdown_event.is_set() or len(all_jobs) >= max_postings:
                                break
                            try:
                                await self.browser.search_jobs(
                                    keyword=keyword,
                                    location=location,
                                    posted_within=posted_within,
                                )
                                search_count += 1
                                remaining = max_postings - len(all_jobs)
                                page_jobs = await self.browser.get_job_listings(max_count=min(remaining, 20))
                                new_count = 0
                                for j in page_jobs:
                                    jid = j.get("job_id", "")
                                    if jid and jid not in seen_job_ids:
                                        all_jobs.append(j)
                                        seen_job_ids.add(jid)
                                        new_count += 1
                                if new_count > 0:
                                    self.log.info(f"  '{keyword}' in {location} → {new_count} new jobs")
                            except Exception as search_err:
                                self.log.warning(f"  '{keyword}' in {location} → failed: {str(search_err)[:60]}. Continuing...")
                                await asyncio.sleep(3)

                self.log.info(f'Search efficiency: {len(all_jobs)} unique from {search_count} searches ({len(all_jobs)/max(search_count,1):.1f} jobs/search)')

            # Source 3: Custom search URLs (additional — boolean queries, job alerts)
            if custom_urls and len(all_jobs) < max_postings:
                self.log.info(f"Scanning {len(custom_urls)} custom URL(s) (additional)...")
                for url in custom_urls:
                    if self._shutdown_event.is_set() or len(all_jobs) >= max_postings:
                        break
                    await self.browser.navigate_to_url(url)
                    remaining = max_postings - len(all_jobs)
                    url_jobs = await self.browser.get_job_listings(max_count=min(remaining, 20))
                    new_count = 0
                    for j in url_jobs:
                        jid = j.get("job_id", "")
                        if jid and jid not in seen_job_ids:
                            all_jobs.append(j)
                            seen_job_ids.add(jid)
                            new_count += 1
                    self.log.info(f"  Custom URL → {new_count} new jobs")

            self.log.info(f"Found {len(all_jobs)} unique jobs to evaluate")
            await self.tracker.log(
                "info", "info",
                f"Discovery complete: {len(all_jobs)} unique jobs to evaluate",
                metadata={"total_found": len(all_jobs)},
            )

            # d. Process each job: open → score → decide → apply/skip
            total_jobs = len(all_jobs)

            # Cloud dedup DB — skip jobs we've already processed
            from linkedin_agent.dedup_db import get_dedup_db
            dedup = get_dedup_db()
            if dedup.connected:
                self.log.info(f"Dedup DB: {dedup.total_seen()} jobs previously seen")

            for idx, job in enumerate(all_jobs, 1):
                if self._shutdown_event.is_set():
                    self.log.info("Shutdown requested, stopping cycle")
                    break

                try:
                    job_title = job.get("title", "Unknown").split('\n')[0][:60]
                    company = job.get("company", "Unknown")
                    job_id = job.get("job_id", "")

                    # Dedup check — skip instantly if we've seen this job before
                    if job_id and dedup.is_seen(job_id):
                        dedup_skipped += 1
                        continue

                    # Anti-detection: random human-paced delay between evaluations
                    if idx > 1:
                        import random
                        delay = random.uniform(3, 6)
                        await asyncio.sleep(delay)

                    self.log.info(f"Scanning {idx}/{total_jobs}: {job_title} @ {company}")

                    # Push real-time progress to dashboard
                    await self.tracker.log(
                        "info", "info",
                        f"Evaluating {idx}/{total_jobs}: {job_title} @ {company}",
                        title=job_title, company=company,
                        metadata={"progress": idx, "total": total_jobs},
                    )

                    # Skip duplicates (old local check)
                    if self.matcher.is_duplicate(company, job_title):
                        self.log.info(f"  → Already applied (duplicate)")
                        dedup.mark_seen(job_id, title=job_title, company=company, status="applied", reason="duplicate")
                        skipped_count += 1
                        self.tally.record(JobStatus.SKIPPED)
                        continue

                    # Open the job page
                    if not job_id:
                        skipped_count += 1
                        self.tally.record(JobStatus.SKIPPED)
                        continue
                    await self.browser.open_job(job_id)

                    # Check if already applied (manual or previous agent run)
                    if await self.browser.is_already_applied():
                        self.log.info(f"  → Already applied (LinkedIn badge detected)")
                        dedup.mark_seen(job_id, title=job_title, company=company, status="applied", reason="already_applied_badge")
                        skipped_count += 1
                        self.tally.record(JobStatus.SKIPPED)
                        continue

                    # Check if external apply
                    is_external = await self.browser.is_external_apply()

                    # Get match score from LinkedIn Premium
                    matched, total = await self.browser.get_match_score()
                    score = matched / total if total > 0 else None
                    job["match_score"] = score

                    # Apply self-learning adjustments
                    if score is not None:
                        score = self.matcher.adjust_score(score, company)
                        job['match_score'] = score

                    # Log score
                    if score is not None:
                        self.log.info(f"  → Match score: {matched}/{total} = {score:.0%}")
                    else:
                        self.log.info(f"  → No score (LinkedIn Premium needed)")

                    # Add ALL to tracker as 'discovered'
                    await self.tracker.push_event(
                        event="discovered", title=job_title, company=company,
                        location=job.get("location"), match_score=score,
                        posting_url=job.get("url"),
                    )
                    discovered_count += 1

                    # Record in dedup DB
                    dedup.mark_seen(
                        job_id, title=job_title, company=company,
                        location=job.get("location", ""),
                        status="discovered", match_score=score,
                        is_easy_apply=not is_external,
                    )

                    # Decision: Easy Apply vs External
                    if is_external:
                        external_url = await self.browser.get_external_apply_url()
                        self.log.info(f"  → External apply: {external_url or 'URL not captured'}")

                        # Track as discovered with external flag
                        await self.tracker.push_event(
                            event="discovered", title=job_title, company=company,
                            location=job.get("location"), match_score=score,
                            posting_url=external_url or job.get("url"),
                        )

                        # If score meets threshold, draft InMail and notify user
                        if score is not None and self.matcher.meets_threshold(score) and inmail_enabled:
                            self.log.info(f"  ✉ High-match external job — drafting InMail + notifying...")
                            await self.send_inmail_for_job(job)

                        # Send Telegram notification for manual apply
                        await self.notifier.send_notification(
                            f"🔗 *External Apply* (manual)\n"
                            f"📋 {job_title} @ {company}\n"
                            f"📍 {job.get('location', 'Unknown')}\n"
                            f"📊 Score: {f'{score:.0%}' if score else 'N/A'}\n"
                            f"🔗 {external_url or job.get('url', 'N/A')}"
                        )

                        # Auto-apply to external jobs if mode allows it
                        if self.config.job_search.auto_apply_external:
                            self.log.info(f'  → Auto-applying to external job...')
                            from linkedin_agent.external_apply import ExternalApplicant
                            ext_applicant = ExternalApplicant(
                                page=self.browser.page,
                                candidate={
                                    'name': self.config.candidate.name,
                                    'email': self.config.candidate.email,
                                    'phone': self.config.candidate.phone,
                                    'resume_filename': self.config.candidate.resume_filename,
                                },
                            )
                            ext_url = external_url or job.get('url', '')
                            if ext_url:
                                ext_result = await ext_applicant.apply(ext_url)
                                self.log.info(f'  → External result: {ext_result["status"]} ({ext_result.get("message", "")})')
                                if ext_result['status'] in ('partial', 'applied'):
                                    await self.notifier.send_notification(
                                        f'🌐 External auto-fill: {job_title} @ {company}\n'
                                        f'Platform: {ext_result.get("platform", "unknown")}\n'
                                        f'Status: {ext_result["message"]}\n'
                                        f'⚠️ Please review and submit manually: {ext_url}'
                                    )
                                # Navigate back to LinkedIn for next job
                                await self.browser.page.goto('https://www.linkedin.com/jobs/', wait_until='domcontentloaded')
                                await asyncio.sleep(2)

                        external_count += 1
                        self.tally.record(JobStatus.SKIPPED)
                        continue

                    if score is None:
                        if self.config.job_search.fallback_scoring:
                            # Use fallback keyword-based scoring
                            from linkedin_agent.fallback_scorer import get_fallback_scorer
                            fallback = get_fallback_scorer(self.config)
                            score = fallback.score_from_job_card(
                                title=job_title,
                                company=company,
                                location=job.get("location", ""),
                            )
                            job["match_score"] = score
                            job["scoring_method"] = "fallback"
                            self.log.info(f"  → Fallback score: {score:.0%} (keyword match)")
                        else:
                            self.log.info(f"  → No score — added to discovered for review")
                            self.tally.record(JobStatus.SKIPPED)
                            continue

                    if not self.matcher.meets_threshold(score):
                        self.log.info(f"  → Not worth applying ({score:.0%} < {self.config.job_search.match_threshold:.0%})")
                        await self.tracker.push_event(
                            event="skipped", title=job_title, company=company,
                            location=job.get("location"), match_score=score,
                            posting_url=job.get("url"),
                        )
                        skipped_count += 1
                        self.tally.record(JobStatus.SKIPPED)
                        continue

                    # Worth applying!
                    scoring_method = job.get("scoring_method", "premium")
                    score_label = f"{score:.0%}" if scoring_method == "fallback" else f"{matched}/{total}"
                    if self.dry_run:
                        self.log.info(f"  ✓ Worth applying! ({score_label}) [DRY RUN — not submitting]")
                        applied_count += 1
                        self.tally.record(JobStatus.SUBMITTED)
                    else:
                        # Check daily cap before submitting
                        if not self.daily_cap.can_apply():
                            self.log.warning(f"  → Daily cap reached, stopping applications")
                            break

                        self.log.info(f"  ✓ Worth applying! ({score_label}) — submitting...")
                        job["id"] = job_id
                        result = await self._applicant.apply_to_job(job)
                        status = self._map_result_status(result.status)
                        self.tally.record(status)

                        if result.status == "submitted":
                            self.daily_cap.record_application()
                            if self.daily_cap.is_near_limit:
                                self.log.warning(
                                    f"  ⚠️ Approaching daily cap: {self.daily_cap.today_count}/{self.daily_cap.daily_limit}"
                                )
                            self.matcher.add_to_applied(company, job_title)
                            await self.tracker.push_event(
                                event="submitted", title=job_title, company=company,
                                location=job.get("location"), match_score=score,
                                posting_url=job.get("url"),
                            )
                            applied_count += 1
                            self.log.info(f"  ✓ Applied successfully!")
                            dedup.mark_applied(job_id)
                            # Send rich per-job Telegram notification
                            await self.notifier.send_job_applied_notification(
                                job_title=job_title,
                                company=company,
                                location=job.get("location", "Unknown"),
                                match_score=score if score is not None else 0.0,
                                posting_url=job.get("url", f"https://www.linkedin.com/jobs/view/{job_id}/"),
                                action="Applied",
                            )
                            # Post-submission InMail: only draft after confirmed apply
                            # so we never message a recruiter about a job we didn't apply to
                            if inmail_enabled:
                                await self.send_inmail_for_job(job)
                        elif result.status == "paused":
                            await self.tracker.push_event(
                                event="paused", title=job_title, company=company,
                                location=job.get("location"), match_score=score,
                                posting_url=job.get("url"),
                            )
                            self.log.info(f"  ⏸ Paused — needs human input")

                except Exception as job_exc:
                    self.tally.record(JobStatus.ERROR)
                    self.log.error(f"  ✗ Error: {str(job_exc)[:80]}")
                    await self.tracker.log_job_error(
                        title=job.get("title", "Unknown")[:60],
                        company=job.get("company", "Unknown"),
                        error=str(job_exc)[:200],
                    )
                    safe_error = str(job_exc)[:80].replace('<', '').replace('>', '')
                    await self.notifier.send_notification(
                        f"❌ Error: {job.get('title', '?')[:30]} @ {job.get('company', '?')}: {safe_error}"
                    )
                    # Add to retry queue for later reattempt
                    self.retry_queue.add(job, error=str(job_exc)[:200])

            # Final summary
            self.log.info("─" * 40)
            self.log.info(f"SUMMARY:")
            self.log.info(f"  Total jobs found:    {total_jobs}")
            self.log.info(f"  Already seen (dedup): {dedup_skipped}")
            self.log.info(f"  New discovered:      {discovered_count}")
            self.log.info(f"  Applied/would apply: {applied_count}")
            self.log.info(f"  External (manual):   {external_count}")
            self.log.info(f"  Skipped (low score): {skipped_count}")
            self.log.info(f"  Retry queue pending: {self.retry_queue.pending_count}")
            self.log.info(f"  Daily cap: {self.daily_cap.today_count}/{self.daily_cap.daily_limit} (remaining: {self.daily_cap.remaining})")
            self.log.info("─" * 40)

            # Sync dedup DB to cloud
            dedup.sync()

            # Process retry queue — attempt previously failed jobs
            self.retry_queue.cleanup_old(max_age_hours=24)
            retry_jobs = self.retry_queue.get_due()
            retry_succeeded = 0
            retry_failed = 0
            if retry_jobs:
                self.log.info(f"Retrying {len(retry_jobs)} previously failed jobs...")
                for rjob in retry_jobs:
                    if self._shutdown_event.is_set():
                        break
                    # Check daily cap before retrying
                    if not self.daily_cap.can_apply():
                        self.log.warning(f"  → Daily cap reached, stopping retries")
                        break
                    rjob_id = rjob.get("job_id") or rjob.get("id", "")
                    rjob_title = rjob.get("title", "Unknown")[:60]
                    rjob_company = rjob.get("company", "Unknown")
                    self.log.info(f"  Retry: {rjob_title} @ {rjob_company}")
                    try:
                        rjob["id"] = rjob_id
                        result = await self._applicant.apply_to_job(rjob)
                        if result.status == "submitted":
                            self.daily_cap.record_application()
                            if self.daily_cap.is_near_limit:
                                self.log.warning(
                                    f"  ⚠️ Approaching daily cap: {self.daily_cap.today_count}/{self.daily_cap.daily_limit}"
                                )
                            self.retry_queue.mark_success(rjob_id)
                            self.matcher.add_to_applied(rjob_company, rjob_title)
                            await self.tracker.push_event(
                                event="submitted", title=rjob_title, company=rjob_company,
                                location=rjob.get("location"), match_score=rjob.get("match_score"),
                                posting_url=rjob.get("url"),
                            )
                            retry_succeeded += 1
                            applied_count += 1
                            self.tally.record(JobStatus.SUBMITTED)
                            self.log.info(f"  ✓ Retry succeeded!")
                            dedup.mark_applied(rjob_id)
                        elif result.status == "paused":
                            self.log.info(f"  ⏸ Retry paused — needs human input")
                            self.tally.record(JobStatus.PAUSED)
                        else:
                            # Non-success, non-error result (e.g. skipped) — remove from queue
                            self.retry_queue.mark_success(rjob_id)
                            self.log.info(f"  → Retry result: {result.status}")
                    except Exception as retry_exc:
                        retry_failed += 1
                        self.log.warning(
                            f"  ✗ Retry failed again: {str(retry_exc)[:60]}"
                        )
                        # Re-add to queue (increments attempt count, may mark permanent failure)
                        self.retry_queue.add(rjob, error=str(retry_exc)[:200])

                self.log.info(
                    f"Retry results: {retry_succeeded} succeeded, "
                    f"{retry_failed} failed, "
                    f"{self.retry_queue.pending_count} still pending"
                )

            # Mark first run as complete (create marker file for subsequent runs)
            if is_first_run:
                marker_file.parent.mkdir(parents=True, exist_ok=True)
                marker_file.touch()
                self.log.info("First run complete — marker saved")

            # Tally report is sent in the finally block via report_tally()

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
            # Check application response statuses before reporting
            try:
                await self.check_response_statuses()
            except Exception as status_exc:
                self.log.warning(f'Response status check failed: {status_exc}')

            # f. Send tally report with full funnel metrics
            await self.report_tally(full_metrics={
                "total_found": total_jobs,
                "dedup_skipped": dedup_skipped,
                "new_discovered": discovered_count,
                "applied": applied_count,
                "external_manual": external_count,
                "skipped_low_score": skipped_count,
                "paused": self.tally.paused,
                "errors": self.tally.errors,
                "retry_pending": self.retry_queue.pending_count,
                "retry_stats": self.retry_queue.get_stats(),
            })

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

        if self.config.scheduler.urgent_mode:
            interval = self.config.scheduler.urgent_interval_minutes

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
                    self.log.info(f"Scheduled scan starting ({now.strftime('%H:%M')})")
                    await self.notifier.send_notification(
                        f"⏰ Scheduled scan starting ({now.strftime('%H:%M')})"
                    )
                    await self.run_scan_cycle()

                    # Send summary to Telegram
                    summary = (
                        f"📊 Scan complete!\n"
                        f"Applied: {self.tally.submitted} | "
                        f"Skipped: {self.tally.skipped} | "
                        f"Errors: {self.tally.errors}\n"
                        f"Next scan: ~{interval}min"
                    )
                    await self.notifier.send_notification(summary)
                else:
                    self.log.info(
                        f"Outside active hours ({active_start}:00–{active_end}:00). "
                        f"Sleeping {interval}min..."
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

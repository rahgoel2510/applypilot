"""LinkedIn-specific pipeline stages — Discovery, Evaluation, Application, Notification.

These stages wrap the existing browser.py, matcher.py, applicant.py, and
telegram_bot.py logic into the event-driven pipeline architecture.

LinkedInDiscoveryStage:
    Scans LinkedIn for jobs using Playwright browser automation.
    Subscribes to CYCLE_STARTED, publishes JOB_DISCOVERED events.

LinkedInEvaluationStage:
    Evaluates discovered jobs: dedup, already-applied check, scoring.
    Subscribes to JOB_DISCOVERED, publishes JOB_QUALIFIED/DISQUALIFIED/EXTERNAL.

LinkedInApplicationStage:
    Submits Easy Apply applications via Playwright.
    Subscribes to JOB_QUALIFIED, publishes JOB_APPLIED/FAILED/PAUSED/CAP_REACHED.

TelegramNotificationStage:
    Sends rich Telegram notifications for pipeline events.
    Subscribes to JOB_APPLIED/EXTERNAL/PAUSED/FAILED/CAP_REACHED (terminal stage).
"""
from __future__ import annotations

import logging
from typing import Any

from .events import EventType, JobEvent, Platform
from .bus import EventBus
from .stages import DiscoveryStage, EvaluationStage, ApplicationStage, NotificationStage

logger = logging.getLogger(__name__)


class LinkedInDiscoveryStage(DiscoveryStage):
    """LinkedIn job discovery using Playwright browser automation.

    Wraps the orchestrator's Source 1–3 logic:
    1. Recommended jobs
    2. Keyword × Location search (OR queries first, then individual)
    3. Custom URLs from config
    """

    name = "linkedin_discovery"

    def __init__(self, bus: EventBus, config: dict[str, Any], browser: Any) -> None:
        self.browser = browser  # LinkedInBrowser instance
        super().__init__(bus, config)

    async def discover_jobs(self, config: dict) -> list[JobEvent]:
        """Scan LinkedIn for jobs matching keywords × locations.

        Replicates the orchestrator's Source 1-3 logic:
        1. Recommended jobs
        2. Keyword × Location search (OR queries first, then individual)
        3. Custom URLs
        """
        events: list[JobEvent] = []
        keywords: list[str] = config.get("keywords", [])
        locations: list[str] = config.get("locations", [])
        max_postings: int = config.get("max_postings_per_run", 50)
        posted_within: str = config.get("posted_within", "24h")
        custom_urls: list[str] = config.get("custom_urls", [])
        collection: str = config.get("collection", "Recommended")
        seen_ids: set[str] = set()

        # ── Source 1: Recommended ──────────────────────────────────
        try:
            await self.browser.navigate_to_jobs(collection=collection)
            rec_jobs = await self.browser.get_job_listings(
                max_count=min(15, max_postings)
            )
            for j in rec_jobs:
                jid = j.get("job_id", "")
                if jid and jid not in seen_ids:
                    seen_ids.add(jid)
                    events.append(self._job_to_event(j))
        except Exception as exc:
            logger.warning("Recommended scan failed: %s", exc)

        # ── Source 2: Keyword × Location (OR queries for each location) ──
        if len(events) < max_postings and len(keywords) > 1:
            combined = " OR ".join(f'"{k}"' for k in keywords)
            for location in locations:
                if len(events) >= max_postings:
                    break
                try:
                    await self.browser.search_jobs(
                        keyword=combined,
                        location=location,
                        posted_within=posted_within,
                    )
                    remaining = max_postings - len(events)
                    page_jobs = await self.browser.get_job_listings(
                        max_count=min(remaining, 25)
                    )
                    for j in page_jobs:
                        jid = j.get("job_id", "")
                        if jid and jid not in seen_ids:
                            seen_ids.add(jid)
                            events.append(self._job_to_event(j))
                except Exception as exc:
                    logger.warning(
                        "OR query search failed for location '%s': %s", location, exc
                    )

        # ── Individual keyword × location (fallback if OR didn't find enough) ──
        if len(events) < int(max_postings * 0.8):
            for keyword in keywords:
                if len(events) >= max_postings:
                    break
                for location in locations:
                    if len(events) >= max_postings:
                        break
                    try:
                        await self.browser.search_jobs(
                            keyword=keyword,
                            location=location,
                            posted_within=posted_within,
                        )
                        remaining = max_postings - len(events)
                        page_jobs = await self.browser.get_job_listings(
                            max_count=min(remaining, 20)
                        )
                        for j in page_jobs:
                            jid = j.get("job_id", "")
                            if jid and jid not in seen_ids:
                                seen_ids.add(jid)
                                events.append(self._job_to_event(j))
                    except Exception as exc:
                        logger.warning(
                            "Individual search failed for '%s' in '%s': %s",
                            keyword,
                            location,
                            exc,
                        )

        # ── Source 3: Custom URLs ──────────────────────────────────
        if custom_urls and len(events) < max_postings:
            for url in custom_urls:
                if len(events) >= max_postings:
                    break
                try:
                    await self.browser.navigate_to_url(url)
                    remaining = max_postings - len(events)
                    url_jobs = await self.browser.get_job_listings(
                        max_count=min(remaining, 20)
                    )
                    for j in url_jobs:
                        jid = j.get("job_id", "")
                        if jid and jid not in seen_ids:
                            seen_ids.add(jid)
                            events.append(self._job_to_event(j))
                except Exception as exc:
                    logger.warning("Custom URL scan failed for '%s': %s", url, exc)

        logger.info("LinkedIn discovery: %d jobs found", len(events))
        return events

    def _job_to_event(self, job: dict) -> JobEvent:
        """Convert a raw job dict from browser to a JobEvent."""
        return JobEvent(
            event_type=EventType.JOB_DISCOVERED,
            platform=Platform.LINKEDIN,
            job_id=job.get("job_id", ""),
            title=job.get("title", "").split("\n")[0][:60],
            company=job.get("company", ""),
            location=job.get("location", ""),
            url=job.get("url", ""),
        )


class LinkedInEvaluationStage(EvaluationStage):
    """Evaluates LinkedIn jobs: dedup, already-applied, scoring, threshold.

    Pipeline flow:
        JOB_DISCOVERED → [dedup] → [already_applied] → [external_check]
                       → [scoring] → [self_learning] → [threshold]
                       → JOB_QUALIFIED / JOB_DISQUALIFIED / JOB_EXTERNAL
    """

    name = "linkedin_evaluation"

    def __init__(
        self,
        bus: EventBus,
        config: dict[str, Any],
        browser: Any,
        matcher: Any,
        fallback_scorer: Any | None = None,
        dedup_db: Any | None = None,
    ) -> None:
        self.browser = browser
        self.matcher = matcher
        self.fallback_scorer = fallback_scorer
        self.dedup_db = dedup_db
        super().__init__(bus, config)

    async def evaluate(self, event: JobEvent) -> JobEvent:
        """Score a discovered job and qualify/disqualify it.

        Steps:
        1. Cloud dedup check (Turso)
        2. Local dedup check (matcher)
        3. Open job page
        4. Already-applied detection
        5. External apply check
        6. Match score (Premium or fallback)
        7. Self-learning adjustment
        8. Threshold qualification
        """
        # ── Step 1: Cloud dedup check ──────────────────────────────
        if self.dedup_db and self.dedup_db.connected and self.dedup_db.is_seen(event.job_id):
            event.event_type = EventType.JOB_DISQUALIFIED
            event.add_marker("dedup_check", status="skipped", reason="already_seen")
            logger.debug("Job %s skipped: already seen in cloud DB", event.job_id)
            return event

        # ── Step 2: Local dedup check ─────────────────────────────
        if self.matcher.is_duplicate(event.company, event.title):
            event.event_type = EventType.JOB_DISQUALIFIED
            event.add_marker("dedup_check", status="skipped", reason="duplicate")
            logger.debug("Job %s skipped: local duplicate", event.job_id)
            return event

        # ── Step 3: Open job page ─────────────────────────────────
        await self.browser.open_job(event.job_id)

        # ── Step 4: Already applied check ─────────────────────────
        if await self.browser.is_already_applied():
            event.event_type = EventType.JOB_DISQUALIFIED
            event.add_marker(
                "already_applied_check", status="skipped", reason="already_applied"
            )
            if self.dedup_db:
                self.dedup_db.mark_seen(
                    event.job_id,
                    title=event.title,
                    company=event.company,
                    status="applied",
                    reason="already_applied_badge",
                )
            logger.debug("Job %s skipped: already applied", event.job_id)
            return event

        # ── Step 5: External apply check ──────────────────────────
        is_external = await self.browser.is_external_apply()
        if is_external:
            external_url = await self.browser.get_external_apply_url()
            event.is_easy_apply = False
            event.external_url = external_url
            event.event_type = EventType.JOB_EXTERNAL
            event.add_marker(
                "external_check", status="completed", external_url=external_url or ""
            )
            logger.info(
                "Job %s (%s) is external apply: %s",
                event.job_id,
                event.company,
                external_url,
            )
            return event

        # ── Step 6: Get match score ───────────────────────────────
        matched, total = await self.browser.get_match_score()
        score = matched / total if total > 0 else None

        if score is not None:
            event.match_score = score
            event.scoring_method = "premium"
        elif self.fallback_scorer:
            score = self.fallback_scorer.score_from_job_card(
                title=event.title, company=event.company, location=event.location
            )
            event.match_score = score
            event.scoring_method = "fallback"

        # ── Step 7: Self-learning adjustment ──────────────────────
        if event.match_score is not None:
            event.match_score = self.matcher.adjust_score(
                event.match_score, event.company
            )

        # ── Step 8: Record in dedup DB ────────────────────────────
        if self.dedup_db:
            self.dedup_db.mark_seen(
                event.job_id,
                title=event.title,
                company=event.company,
                location=event.location,
                status="discovered",
                match_score=event.match_score,
                is_easy_apply=True,
            )

        # ── Step 9: Threshold check ──────────────────────────────
        threshold = self.config.get("match_threshold", 0.80)
        if event.match_score is not None and event.match_score >= threshold:
            event.event_type = EventType.JOB_QUALIFIED
            event.add_marker(
                "evaluation",
                status="qualified",
                score=event.match_score,
                method=event.scoring_method,
            )
            logger.info(
                "Job %s (%s at %s) QUALIFIED: %.0f%% (%s)",
                event.job_id,
                event.title,
                event.company,
                event.match_score * 100,
                event.scoring_method,
            )
        else:
            event.event_type = EventType.JOB_DISQUALIFIED
            event.add_marker(
                "evaluation",
                status="disqualified",
                score=event.match_score,
                threshold=threshold,
            )
            logger.debug(
                "Job %s (%s at %s) disqualified: score=%s threshold=%.0f%%",
                event.job_id,
                event.title,
                event.company,
                f"{event.match_score * 100:.0f}%" if event.match_score else "None",
                threshold * 100,
            )

        return event


# ─── Application ───────────────────────────────────────────────


class LinkedInApplicationStage(ApplicationStage):
    """Submits Easy Apply applications via Playwright."""

    name = "linkedin_application"

    def __init__(
        self,
        bus: EventBus,
        config: dict[str, Any],
        applicant: Any,
        daily_cap: Any,
        matcher: Any,
    ) -> None:
        self.applicant = applicant  # ApplicationExecutor instance
        self.daily_cap = daily_cap  # DailyApplicationCap instance
        self.matcher = matcher  # JobMatcher instance (for dedup on success)
        super().__init__(bus, config)

    async def apply(self, event: JobEvent) -> JobEvent:
        """Submit Easy Apply application for a qualified job."""
        # Check daily cap
        if not self.daily_cap.can_apply():
            event.event_type = EventType.CAP_REACHED
            event.add_marker("daily_cap", status="blocked", count=self.daily_cap.today_count)
            return event

        # Prepare job dict for applicant
        job_dict = {
            "id": event.job_id,
            "job_id": event.job_id,
            "title": event.title,
            "company": event.company,
            "location": event.location,
            "url": event.url,
            "match_score": event.match_score,
        }

        # Submit application
        result = await self.applicant.apply_to_job(job_dict)

        if result.status == "submitted":
            event.event_type = EventType.JOB_APPLIED
            event.add_marker("application", status="submitted")
            self.daily_cap.record_application()
            self.matcher.add_to_applied(event.company, event.title)
        elif result.status == "paused":
            event.event_type = EventType.JOB_PAUSED
            event.add_marker(
                "application",
                status="paused",
                blocking_fields=result.blocking_fields,
            )
        else:
            event.event_type = EventType.JOB_FAILED
            event.error = result.error_message or result.status
            event.add_marker("application", status="failed", reason=result.status)

        return event


# ─── Notification ──────────────────────────────────────────────


class TelegramNotificationStage(NotificationStage):
    """Sends rich Telegram notifications for all pipeline events."""

    name = "telegram_notification"

    def __init__(self, bus: EventBus, config: dict[str, Any], notifier: Any) -> None:
        self.notifier = notifier  # TelegramNotifier instance
        super().__init__(bus, config)

    async def notify(self, event: JobEvent) -> None:
        """Send Telegram notification based on event type."""
        if event.event_type == EventType.JOB_APPLIED:
            await self.notifier.send_job_applied_notification(
                job_title=event.title,
                company=event.company,
                location=event.location,
                match_score=event.match_score or 0.0,
                posting_url=event.url,
                action="Applied",
            )
        elif event.event_type == EventType.JOB_EXTERNAL:
            score_str = f"{event.match_score:.0%}" if event.match_score else "N/A"
            await self.notifier.send_notification(
                f"🔗 *External Apply* (manual)\n"
                f"📋 {event.title} @ {event.company}\n"
                f"📍 {event.location}\n"
                f"📊 Score: {score_str}\n"
                f"🔗 {event.external_url or event.url}"
            )
        elif event.event_type == EventType.JOB_PAUSED:
            markers = event.stage_markers
            fields: list[str] = []
            for m in markers:
                if m.metadata.get("blocking_fields"):
                    fields = m.metadata["blocking_fields"]
            await self.notifier.send_notification(
                f"⏸️ *Paused*: {event.title} @ {event.company}\n"
                f'Fields: {", ".join(fields[:3]) if fields else "unknown"}'
            )
        elif event.event_type == EventType.JOB_FAILED:
            await self.notifier.send_notification(
                f"❌ *Failed*: {event.title} @ {event.company}\n"
                f'Error: {(event.error or "unknown")[:80]}'
            )
        elif event.event_type == EventType.CAP_REACHED:
            await self.notifier.send_notification(
                "⚠️ Daily cap reached. Pausing applications until tomorrow."
            )

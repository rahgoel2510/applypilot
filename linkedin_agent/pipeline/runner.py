"""Pipeline runner — bootstraps stages, middleware, and runs scan cycles.

Replaces the monolithic orchestrator with a clean event-driven flow.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from linkedin_agent.config import Settings, get_config
from linkedin_agent.browser import LinkedInBrowser
from linkedin_agent.matcher import JobMatcher
from linkedin_agent.applicant import ApplicationExecutor
from linkedin_agent.telegram_bot import TelegramNotifier
from linkedin_agent.fallback_scorer import get_fallback_scorer
from linkedin_agent.daily_cap import get_daily_cap
from linkedin_agent.dedup_db import get_dedup_db
from linkedin_agent.tracker_client import get_tracker
from linkedin_agent.inmail import InMailDrafter

from .events import EventType, JobEvent, Platform
from .bus import EventBus
from .linkedin_stages import (
    LinkedInDiscoveryStage,
    LinkedInEvaluationStage,
    LinkedInApplicationStage,
    TelegramNotificationStage,
)

logger = logging.getLogger(__name__)


# ─── Middleware ───────────────────────────────────────────────


async def logging_middleware(event: JobEvent) -> JobEvent:
    """Log every event passing through the bus."""
    logger.debug(
        "[%s] %s: %s @ %s (score=%s)",
        event.event_type.value,
        event.event_id,
        event.title[:40],
        event.company[:20],
        f"{event.match_score:.0%}" if event.match_score else "N/A",
    )
    return event


async def tracker_middleware(event: JobEvent) -> JobEvent:
    """Push events to the tracker API for dashboard visibility."""
    tracker = get_tracker()
    event_map = {
        EventType.JOB_DISCOVERED: "discovered",
        EventType.JOB_APPLIED: "submitted",
        EventType.JOB_EXTERNAL: "discovered",
        EventType.JOB_PAUSED: "paused",
    }
    tracker_event = event_map.get(event.event_type)
    if tracker_event:
        await tracker.push_event(
            event=tracker_event,
            title=event.title,
            company=event.company,
            location=event.location,
            match_score=event.match_score,
            posting_url=event.url,
        )
    return event


class PipelineRunner:
    """Bootstraps the event-driven pipeline and runs scan cycles.

    Usage:
        runner = PipelineRunner(config)
        await runner.setup()
        await runner.run_cycle()
        await runner.shutdown()
    """

    def __init__(self, config: Settings | None = None, dry_run: bool = False) -> None:
        self.config = config or get_config(validate=True)
        self.dry_run = dry_run
        self.bus = EventBus()

        # Modules (initialized in setup)
        self.browser: LinkedInBrowser | None = None
        self.matcher: JobMatcher | None = None
        self.notifier: TelegramNotifier | None = None
        self.daily_cap = get_daily_cap(daily_limit=self.config.job_search.daily_application_limit)
        self.dedup_db = get_dedup_db()

        # Stages (initialized in setup)
        self._stages: list = []
        self._shutdown_event = asyncio.Event()

    async def setup(self) -> None:
        """Initialize browser, modules, stages, and wire the pipeline."""
        logger.info("Pipeline setup starting...")

        # Initialize browser
        self.browser = LinkedInBrowser()
        await self.browser.launch()
        await self.browser.login(
            email=self.config.linkedin_email,
            password=self.config.linkedin_password,
        )

        # Initialize matcher
        self.matcher = JobMatcher(
            threshold=self.config.job_search.match_threshold,
            target_companies=self.config.self_learning.target_companies,
            blocklist_companies=self.config.self_learning.blocklist_companies,
            target_boost=self.config.self_learning.target_boost,
            blocklist_penalty=self.config.self_learning.blocklist_penalty,
        )

        # Initialize notifier
        self.notifier = TelegramNotifier(
            bot_token=self.config.telegram.bot_token,
            chat_id=self.config.telegram.chat_id,
        )

        # Initialize fallback scorer
        fallback = get_fallback_scorer(self.config) if self.config.job_search.fallback_scoring else None

        # Register middleware
        self.bus.use(logging_middleware)
        self.bus.use(tracker_middleware)

        # Register stages
        search_config = {
            "keywords": list(self.config.job_search.keywords),
            "locations": list(self.config.job_search.locations),
            "max_postings_per_run": self.config.job_search.max_postings_per_run,
            "posted_within": self.config.job_search.posted_within,
            "custom_urls": list(self.config.job_search.custom_urls),
            "collection": self.config.job_search.collection,
            "match_threshold": self.config.job_search.match_threshold,
        }

        discovery = LinkedInDiscoveryStage(self.bus, search_config, self.browser)
        evaluation = LinkedInEvaluationStage(
            self.bus, search_config, self.browser, self.matcher, fallback, self.dedup_db
        )

        if not self.dry_run:
            applicant = ApplicationExecutor(
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
                        "sensitive_field_answers": dict(self.config.candidate.sensitive_field_answers),
                        "human_input_timeout": self.config.candidate.human_input_timeout,
                        "resume_mapping": list(self.config.candidate.resume_mapping),
                        "skills": list(self.config.candidate.skills),
                    },
                    "job_search": {
                        "match_threshold": self.config.job_search.match_threshold,
                        "skip_external_apply": self.config.job_search.skip_external_apply,
                        "keywords": list(self.config.job_search.keywords),
                    },
                    "telegram": {
                        "notify_on_submit": self.config.telegram.notify_on_submit,
                        "notify_on_pause": self.config.telegram.notify_on_pause,
                    },
                },
            )
            application = LinkedInApplicationStage(
                self.bus, search_config, applicant, self.daily_cap, self.matcher
            )
            self._stages.append(application)

        notification = TelegramNotificationStage(self.bus, search_config, self.notifier)

        self._stages.extend([discovery, evaluation, notification])

        logger.info("Pipeline setup complete: %d stages registered", len(self._stages))

    async def run_cycle(self) -> dict[str, Any]:
        """Run one scan cycle through the event-driven pipeline."""
        logger.info("Pipeline cycle starting...")
        t0 = time.time()

        # Check daily cap before starting
        if self.daily_cap.is_at_limit:
            logger.warning("Daily cap reached — skipping cycle")
            await self.notifier.send_notification(
                "⚠️ Daily cap reached. Skipping this cycle."
            )
            return {"status": "cap_reached", "duration_sec": 0}

        # Fire CYCLE_STARTED event — triggers discovery
        cycle_event = JobEvent(
            event_type=EventType.CYCLE_STARTED,
            platform=Platform.LINKEDIN,
        )
        await self.bus.publish(cycle_event)

        # Persist event log
        self.bus.save_state()

        duration = int(time.time() - t0)
        stats = self.bus.stats

        logger.info(
            "Pipeline cycle complete in %ds: %s",
            duration,
            {k: v for k, v in stats.items() if v > 0},
        )

        return {
            "status": "completed",
            "duration_sec": duration,
            "stats": stats,
            "dead_letter_count": self.bus.dead_letter_count,
        }

    async def shutdown(self) -> None:
        """Clean up resources."""
        logger.info("Pipeline shutting down...")
        self._shutdown_event.set()
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
        self.bus.save_state()
        logger.info("Pipeline shutdown complete")

    def request_shutdown(self) -> None:
        """Signal the runner to stop at the next opportunity."""
        self._shutdown_event.set()

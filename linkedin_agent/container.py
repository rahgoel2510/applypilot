"""Dependency Injection container.

Wires protocol implementations together. Supports overrides for testing.
All services are lazily instantiated and cached (singleton per container).

Usage:
    container = Container(config)
    notifier = container.notifier        # lazy-creates TelegramNotifier
    container.override("notifier", mock)  # swap for testing
"""

from __future__ import annotations

import logging
from typing import Any

from linkedin_agent.config import Settings
from linkedin_agent.protocols import (
    ApplicationExecutorProtocol,
    BrowserSession,
    DailyCapProtocol,
    DedupStore,
    FallbackScorerProtocol,
    InMailDrafterProtocol,
    JobScorer,
    Notifier,
    RetryQueueProtocol,
    TrackerClientProtocol,
)

logger = logging.getLogger(__name__)


class Container:
    """Dependency injection container with lazy initialization and override support.

    All dependencies are created on first access and cached.
    Use override() to swap implementations for testing.
    """

    def __init__(self, config: Settings) -> None:
        self._config = config
        self._cache: dict[str, Any] = {}
        self._overrides: dict[str, Any] = {}

    @property
    def config(self) -> Settings:
        return self._config

    def override(self, name: str, instance: Any) -> None:
        """Override a dependency with a custom implementation (for testing)."""
        self._overrides[name] = instance
        # Clear cache so next access returns override
        self._cache.pop(name, None)

    def reset(self) -> None:
        """Reset all overrides and cached instances."""
        self._overrides.clear()
        self._cache.clear()

    def _get_or_create(self, name: str, factory) -> Any:
        """Get from override, cache, or create via factory."""
        if name in self._overrides:
            return self._overrides[name]
        if name not in self._cache:
            self._cache[name] = factory()
        return self._cache[name]

    # ─── Service Accessors ──────────────────────────────────────────

    @property
    def browser(self) -> BrowserSession:
        def factory():
            from linkedin_agent.browser import LinkedInBrowser
            return LinkedInBrowser()
        return self._get_or_create("browser", factory)

    @property
    def scorer(self) -> JobScorer:
        def factory():
            from linkedin_agent.matcher import JobMatcher
            return JobMatcher(
                threshold=self._config.job_search.match_threshold,
                target_companies=self._config.self_learning.target_companies,
                blocklist_companies=self._config.self_learning.blocklist_companies,
                target_boost=self._config.self_learning.target_boost,
                blocklist_penalty=self._config.self_learning.blocklist_penalty,
            )
        return self._get_or_create("scorer", factory)

    @property
    def fallback_scorer(self) -> FallbackScorerProtocol:
        def factory():
            from linkedin_agent.fallback_scorer import get_fallback_scorer
            return get_fallback_scorer(self._config)
        return self._get_or_create("fallback_scorer", factory)

    @property
    def notifier(self) -> Notifier:
        def factory():
            from linkedin_agent.telegram_bot import TelegramNotifier
            return TelegramNotifier(
                bot_token=self._config.telegram.bot_token,
                chat_id=self._config.telegram.chat_id,
            )
        return self._get_or_create("notifier", factory)

    @property
    def dedup(self) -> DedupStore:
        def factory():
            from linkedin_agent.dedup_db import get_dedup_db
            return get_dedup_db()
        return self._get_or_create("dedup", factory)

    @property
    def daily_cap(self) -> DailyCapProtocol:
        def factory():
            from linkedin_agent.daily_cap import get_daily_cap
            return get_daily_cap(daily_limit=self._config.job_search.daily_application_limit)
        return self._get_or_create("daily_cap", factory)

    @property
    def retry_queue(self) -> RetryQueueProtocol:
        def factory():
            from linkedin_agent.retry_queue import RetryQueue
            return RetryQueue()
        return self._get_or_create("retry_queue", factory)

    @property
    def tracker(self) -> TrackerClientProtocol:
        def factory():
            from linkedin_agent.tracker_client import get_tracker
            return get_tracker()
        return self._get_or_create("tracker", factory)

    @property
    def inmail(self) -> InMailDrafterProtocol:
        def factory():
            from linkedin_agent.inmail import InMailDrafter
            return InMailDrafter(self._config)
        return self._get_or_create("inmail", factory)

    def create_applicant(self, browser: BrowserSession, scorer: JobScorer, notifier: Notifier) -> ApplicationExecutorProtocol:
        """Create an ApplicationExecutor (not cached — lifecycle-bound to scan cycle)."""
        if "applicant" in self._overrides:
            return self._overrides["applicant"]
        from linkedin_agent.applicant import ApplicationExecutor
        return ApplicationExecutor(
            browser=browser,
            matcher=scorer,
            notifier=notifier,
            config={
                "candidate": {
                    "name": self._config.candidate.name,
                    "email": self._config.candidate.email,
                    "phone": self._config.candidate.phone,
                    "resume_filename": self._config.candidate.resume_filename,
                    "notice_period": self._config.candidate.notice_period,
                    "willing_to_relocate": self._config.candidate.willing_to_relocate,
                    "work_authorization": self._config.candidate.work_authorization,
                    "preferred_cities": list(self._config.candidate.preferred_cities),
                },
                "job_search": {
                    "match_threshold": self._config.job_search.match_threshold,
                    "skip_external_apply": self._config.job_search.skip_external_apply,
                },
                "telegram": {
                    "notify_on_submit": self._config.telegram.notify_on_submit,
                    "notify_on_pause": self._config.telegram.notify_on_pause,
                },
            },
        )

"""Protocol definitions for dependency injection.

All services depend ONLY on these protocols, never on concrete implementations.
This enables:
- Easy testing (mock any dependency)
- Loose coupling (swap implementations without touching consumers)
- Clear contracts between modules
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable


@runtime_checkable
class BrowserSession(Protocol):
    """Protocol for browser automation session."""

    async def launch(self) -> None: ...
    async def close(self) -> None: ...
    async def login(self, email: str, password: str) -> None: ...
    async def navigate_to_jobs(self, collection: str = "Recommended") -> None: ...
    async def search_jobs(self, keyword: str, location: str, posted_within: str = "week") -> None: ...
    async def get_job_listings(self, max_count: int = 25) -> list[dict[str, Any]]: ...
    async def navigate_to_url(self, url: str) -> None: ...
    async def check_application_statuses(self, max_check: int = 30) -> list[dict[str, Any]]: ...


@runtime_checkable
class JobScorer(Protocol):
    """Protocol for job matching/scoring."""

    def meets_threshold(self, score: float) -> bool: ...
    def is_duplicate(self, company: str, title: str) -> bool: ...
    def add_to_applied(self, company: str, title: str) -> None: ...


@runtime_checkable
class FallbackScorerProtocol(Protocol):
    """Protocol for keyword-based fallback scoring."""

    def score_from_job_card(self, title: str, company: str, location: str) -> float: ...


@runtime_checkable
class ApplicationExecutorProtocol(Protocol):
    """Protocol for submitting job applications."""

    async def apply_to_job(self, job: dict[str, Any]) -> Any: ...


@runtime_checkable
class Notifier(Protocol):
    """Protocol for sending notifications (Telegram, etc.)."""

    async def send_notification(self, message: str) -> None: ...
    async def send_tally_report(self, tally: dict[str, int]) -> None: ...
    async def send_job_applied_notification(
        self,
        job_title: str,
        company: str,
        location: str,
        match_score: float,
        posting_url: str,
        action: str = "Applied",
    ) -> None: ...
    async def send_inmail_draft(
        self,
        job_title: str,
        company: str,
        recruiter: str,
        draft: str,
    ) -> None: ...


@runtime_checkable
class DedupStore(Protocol):
    """Protocol for deduplication persistence."""

    @property
    def connected(self) -> bool: ...
    def is_seen(self, job_id: str) -> bool: ...
    def mark_seen(self, job_id: str, **kwargs: Any) -> None: ...
    def mark_applied(self, job_id: str) -> None: ...
    def mark_skipped(self, job_id: str, reason: str = "") -> None: ...
    def sync(self) -> None: ...
    def total_seen(self) -> int: ...
    def stats(self) -> dict[str, int]: ...


@runtime_checkable
class DailyCapProtocol(Protocol):
    """Protocol for daily application rate limiting."""

    @property
    def daily_limit(self) -> int: ...
    @property
    def today_count(self) -> int: ...
    @property
    def remaining(self) -> int: ...
    @property
    def is_at_limit(self) -> bool: ...
    @property
    def is_near_limit(self) -> bool: ...
    def can_apply(self) -> bool: ...
    def record_application(self) -> None: ...


@runtime_checkable
class RetryQueueProtocol(Protocol):
    """Protocol for retry queue with exponential backoff."""

    @property
    def pending_count(self) -> int: ...
    def add(self, job: dict, error: str, max_retries: int = 3) -> None: ...
    def get_due(self) -> list[dict]: ...
    def mark_success(self, job_id: str) -> None: ...
    def cleanup_old(self, max_age_hours: int = 24) -> None: ...
    def get_stats(self) -> dict[str, Any]: ...


@runtime_checkable
class TrackerClientProtocol(Protocol):
    """Protocol for tracker API integration."""

    async def push_event(
        self,
        event: str,
        title: str,
        company: str,
        location: str | None = None,
        match_score: float | None = None,
        posting_url: str | None = None,
    ) -> bool: ...

    async def log(
        self,
        event_type: str,
        severity: str = "info",
        message: str = "",
        title: str | None = None,
        company: str | None = None,
        stage: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool: ...

    async def log_cycle_start(self, max_postings: int, collection: str) -> bool: ...
    async def log_cycle_end(self, submitted: int, skipped: int, paused: int, errors: int, duration_sec: int) -> bool: ...
    async def log_job_error(self, title: str, company: str, error: str) -> bool: ...
    async def log_inmail_drafted(self, title: str, company: str, recruiter: str) -> bool: ...
    async def log_agent_start(self, interval_minutes: int, active_hours: str) -> bool: ...
    async def push_inmail_draft(self, job_title: str, company: str, recruiter: str, draft_text: str, job_id: str | None = None) -> bool: ...


@runtime_checkable
class InMailDrafterProtocol(Protocol):
    """Protocol for AI-powered InMail drafting."""

    def get_candidate_summary(self) -> str: ...
    async def draft_inmail(
        self,
        job_title: str,
        company: str,
        recruiter_name: str,
        job_description: str,
        candidate_summary: str,
    ) -> str: ...


@runtime_checkable
class AnswerGeneratorProtocol(Protocol):
    """Protocol for AI-generated form field answers."""

    @staticmethod
    def is_ai_answerable(field_label: str) -> bool: ...
    async def generate_answer(self, field_label: str, job_title: str, company: str) -> str: ...


@runtime_checkable
class HealthCheck(Protocol):
    """Protocol for service health checking."""

    async def check_health(self) -> dict[str, Any]: ...

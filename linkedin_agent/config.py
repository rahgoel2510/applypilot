"""Configuration module for LinkedIn Job Agent.

Loads settings from config.yaml and environment variables (.env),
validates required secrets, and provides a typed singleton accessor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
ENV_FILE = PROJECT_ROOT / ".env"

# ---------------------------------------------------------------------------
# Required environment variables (must be set for the agent to operate)
# ---------------------------------------------------------------------------

REQUIRED_ENV_VARS: list[str] = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "OPENAI_API_KEY",
    "LINKEDIN_EMAIL",
    "LINKEDIN_PASSWORD",
]

# ---------------------------------------------------------------------------
# Sub-config dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateConfig:
    """Candidate profile settings."""

    name: str = ""
    email: str = ""
    phone: str = ""
    resume_filename: str = "resume.pdf"
    resume_mapping: list = field(default_factory=list)  # [{keywords: [...], resume: "..."}]
    notice_period: str = "Immediate"
    willing_to_relocate: bool = True
    work_authorization: str = "Authorized to work"
    preferred_cities: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    sensitive_field_answers: dict = field(default_factory=dict)
    human_input_timeout: int = 300


@dataclass(frozen=True)
class JobSearchConfig:
    """Job search behaviour settings."""

    keywords: list[str] = field(default_factory=lambda: ["Software Engineer"])
    custom_urls: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=lambda: ["India"])
    match_threshold: float = 0.80
    max_postings_per_run: int = 50
    collection: str = "Recommended"
    skip_external_apply: bool = False
    track_external_apply: bool = True
    posted_within: str = "week"  # day, week, month
    initial_scan_window: str = "week"  # Used on first-ever run (day, week, month)
    fallback_scoring: bool = True
    daily_application_limit: int = 80  # Conservative daily cap (LinkedIn soft limit ~100)
    search_mode: str = "active"  # aggressive, active, passive, or custom
    auto_apply_external: bool = False  # Auto-apply to external job links


@dataclass(frozen=True)
class SchedulerConfig:
    """Scheduler timing settings."""

    interval_minutes: int = 60
    active_hours_start: int = 9
    active_hours_end: int = 22
    urgent_mode: bool = False
    urgent_interval_minutes: int = 30
    urgent_max_postings: int = 100
    urgent_duration_days: int = 7


@dataclass(frozen=True)
class TelegramConfig:
    """Telegram notification settings."""

    bot_token: str = ""
    chat_id: str = ""
    notify_on_submit: bool = True
    notify_on_pause: bool = True
    notify_on_skip: bool = False
    tally_interval_minutes: int = 30


@dataclass(frozen=True)
class InmailConfig:
    """InMail outreach settings."""

    enabled: bool = True
    tone: str = "professional"
    max_length: int = 300


@dataclass(frozen=True)
class SelfLearningConfig:
    """Self-learning seed configuration for target/blocklist companies."""

    target_companies: list[str] = field(default_factory=list)
    blocklist_companies: list[str] = field(default_factory=list)
    target_boost: float = 0.15
    blocklist_penalty: float = 0.20


# ---------------------------------------------------------------------------
# Top-level Settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Settings:
    """Aggregated application settings (singleton via get_config)."""

    candidate: CandidateConfig = field(default_factory=CandidateConfig)
    job_search: JobSearchConfig = field(default_factory=JobSearchConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    inmail: InmailConfig = field(default_factory=InmailConfig)
    self_learning: SelfLearningConfig = field(default_factory=SelfLearningConfig)

    # Secrets (loaded from env)
    openai_api_key: str = ""
    linkedin_email: str = ""
    linkedin_password: str = ""

    # Meta
    project_root: Path = PROJECT_ROOT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Raised when configuration is invalid or incomplete."""


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file. Returns empty dict if file is missing."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def _env(key: str, default: str = "") -> str:
    """Get an environment variable, supporting override over .env values."""
    return os.environ.get(key, default)


def _env_list(key: str, default: list) -> list:
    """Get a comma-separated env var as a list. Falls back to default if not set."""
    val = os.environ.get(key, "")
    if val:
        return [s.strip() for s in val.split(",") if s.strip()]
    return default


def _env_bool(key: str, default: bool) -> bool:
    """Get a boolean from env var. Supports 'true'/'false'/'1'/'0'."""
    val = os.environ.get(key, "")
    if not val:
        return default
    return val.lower() in ("true", "1", "yes")


def _normalize_threshold(value: float) -> float:
    """Normalize match threshold to 0.0-1.0 range.

    The UI slider may send integer percentages (e.g. 70, 80) while the agent
    expects a float (0.70, 0.80). If the value is > 1.0, treat it as a
    percentage and divide by 100.
    """
    if value > 1.0:
        return value / 100.0
    return value


def _validate_env() -> None:
    """Check for required environment variables.
    
    Logs a warning for missing vars but does NOT raise.
    Settings may be configured via the dashboard DB instead of .env.
    """
    missing = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
    if missing:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Environment vars not set: {', '.join(missing)}. "
            f"These may be configured via the dashboard Settings page."
        )


def _build_settings(yaml_data: dict[str, Any]) -> Settings:
    """Construct a Settings instance from parsed YAML + environment."""

    # --- Candidate ---
    c = yaml_data.get("candidate", {})
    candidate = CandidateConfig(
        name=_env("CANDIDATE_NAME", c.get("name", "")),
        email=_env("CANDIDATE_EMAIL", c.get("email", "")),
        phone=_env("CANDIDATE_PHONE", c.get("phone", "")),
        resume_filename=c.get("resume_filename", "resume.pdf"),
        resume_mapping=c.get("resume_mapping", []),
        notice_period=c.get("notice_period", "Immediate"),
        willing_to_relocate=c.get("willing_to_relocate", True),
        work_authorization=c.get("work_authorization", "Authorized to work"),
        preferred_cities=c.get("preferred_cities", []),
        skills=c.get("skills", []),
        sensitive_field_answers=c.get("sensitive_field_answers", {}),
        human_input_timeout=int(c.get("human_input_timeout", 300)),
    )

    # --- Job search ---
    js = yaml_data.get("job_search", {})

    # Apply search mode preset ONLY for fields not explicitly set in yaml
    search_mode = _env("SEARCH_MODE", js.get("search_mode", "active"))
    if search_mode and search_mode != "custom":
        from linkedin_agent.search_modes import get_mode_config, SearchMode
        try:
            preset = get_mode_config(search_mode)
            # Only fill in values that the user hasn't explicitly configured
            if "match_threshold" not in js:
                js["match_threshold"] = preset.match_threshold
            if "max_postings_per_run" not in js:
                js["max_postings_per_run"] = preset.max_postings_per_run
            if "daily_application_limit" not in js:
                js["daily_application_limit"] = preset.daily_application_limit
            if "auto_apply_external" not in js:
                js["auto_apply_external"] = preset.auto_apply_external
            if "fallback_scoring" not in js:
                js["fallback_scoring"] = preset.fallback_scoring
            # Scheduler overrides (only if scheduler section is empty/missing)
            sc_section = yaml_data.get("scheduler", {})
            if "interval_minutes" not in sc_section:
                sc_section["interval_minutes"] = preset.interval_minutes
            if "active_hours_start" not in sc_section:
                sc_section["active_hours_start"] = preset.active_hours_start
            if "active_hours_end" not in sc_section:
                sc_section["active_hours_end"] = preset.active_hours_end
            yaml_data["scheduler"] = sc_section
        except (ValueError, KeyError):
            pass  # Invalid mode name — ignore

    job_search = JobSearchConfig(
        keywords=_env_list("SEARCH_KEYWORDS", js.get("keywords", ["Software Engineer"])),
        custom_urls=js.get("custom_urls", []),
        locations=_env_list("SEARCH_LOCATIONS", js.get("locations", ["India"])),
        match_threshold=_normalize_threshold(float(_env("MATCH_THRESHOLD", str(js.get("match_threshold", 0.80))))),
        max_postings_per_run=int(_env("MAX_POSTINGS_PER_RUN", str(js.get("max_postings_per_run", 50)))),
        collection=js.get("collection", "Recommended"),
        skip_external_apply=_env_bool("SKIP_EXTERNAL_APPLY", js.get("skip_external_apply", False)),
        track_external_apply=_env_bool("TRACK_EXTERNAL_APPLY", js.get("track_external_apply", True)),
        posted_within=_env("POSTED_WITHIN", js.get("posted_within", "week")) or "week",
        initial_scan_window=_env("INITIAL_SCAN_WINDOW", js.get("initial_scan_window", "week")) or "week",
        fallback_scoring=_env_bool("FALLBACK_SCORING", js.get("fallback_scoring", True)),
        daily_application_limit=int(_env("DAILY_APPLICATION_LIMIT", str(js.get("daily_application_limit", 80)))),
        search_mode=search_mode,
        auto_apply_external=_env_bool("AUTO_APPLY_EXTERNAL", js.get("auto_apply_external", False)),
    )

    # --- Scheduler ---
    sc = yaml_data.get("scheduler", {})
    scheduler = SchedulerConfig(
        interval_minutes=int(_env("SCHEDULER_INTERVAL", str(sc.get("interval_minutes", 60)))),
        active_hours_start=int(sc.get("active_hours_start", 9)),
        active_hours_end=int(sc.get("active_hours_end", 22)),
        urgent_mode=sc.get("urgent_mode", False),
        urgent_interval_minutes=int(sc.get("urgent_interval_minutes", 30)),
        urgent_max_postings=int(sc.get("urgent_max_postings", 100)),
        urgent_duration_days=int(sc.get("urgent_duration_days", 7)),
    )

    # --- Telegram ---
    tg = yaml_data.get("telegram", {})
    telegram = TelegramConfig(
        bot_token=_env("TELEGRAM_BOT_TOKEN"),
        chat_id=_env("TELEGRAM_CHAT_ID"),
        notify_on_submit=tg.get("notify_on_submit", True),
        notify_on_pause=tg.get("notify_on_pause", True),
        notify_on_skip=tg.get("notify_on_skip", False),
        tally_interval_minutes=int(tg.get("tally_interval_minutes", 30)),
    )

    # --- InMail ---
    im = yaml_data.get("inmail", {})
    inmail = InmailConfig(
        enabled=im.get("enabled", True),
        tone=im.get("tone", "professional"),
        max_length=int(im.get("max_length", 300)),
    )

    # --- Self-learning ---
    sl = yaml_data.get("self_learning", {})
    self_learning = SelfLearningConfig(
        target_companies=sl.get("target_companies", []),
        blocklist_companies=sl.get("blocklist_companies", []),
        target_boost=float(sl.get("target_boost", 0.15)),
        blocklist_penalty=float(sl.get("blocklist_penalty", 0.20)),
    )

    return Settings(
        candidate=candidate,
        job_search=job_search,
        scheduler=scheduler,
        telegram=telegram,
        inmail=inmail,
        self_learning=self_learning,
        openai_api_key=_env("OPENAI_API_KEY"),
        linkedin_email=_env("LINKEDIN_EMAIL"),
        linkedin_password=_env("LINKEDIN_PASSWORD"),
        project_root=PROJECT_ROOT,
    )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_settings_instance: Settings | None = None


def get_config(*, validate: bool = True, reload: bool = False) -> Settings:
    """Return the application Settings singleton.

    Args:
        validate: If True (default), raises ConfigError when required
                  environment variables are missing.
        reload:   If True, forces a fresh load from disk/env (useful in tests).

    Returns:
        The Settings instance.
    """
    global _settings_instance  # noqa: PLW0603

    if _settings_instance is not None and not reload:
        return _settings_instance

    # Load .env into os.environ (existing env vars take precedence)
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)

    if validate:
        _validate_env()

    yaml_data = _load_yaml(CONFIG_FILE)
    _settings_instance = _build_settings(yaml_data)
    return _settings_instance


def reset_config() -> None:
    """Reset the singleton (primarily for testing)."""
    global _settings_instance  # noqa: PLW0603
    _settings_instance = None

"""Job search mode presets — Aggressive, Active, Passive.

Each mode configures the agent's behavior automatically:
- Aggressive: Maximum throughput, lower threshold, frequent scans
- Active: Balanced for someone actively looking (default)
- Passive: Minimal disruption, high threshold, infrequent scans
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class SearchMode(str, Enum):
    AGGRESSIVE = "aggressive"
    ACTIVE = "active"
    PASSIVE = "passive"


@dataclass(frozen=True)
class ModeConfig:
    """Auto-configured parameters for a search mode."""
    mode: SearchMode
    label: str
    description: str
    
    # Timing
    interval_minutes: int
    active_hours_start: int
    active_hours_end: int
    
    # Volume
    max_postings_per_run: int
    daily_application_limit: int
    
    # Scoring
    match_threshold: float
    
    # External jobs
    auto_apply_external: bool
    track_external: bool
    
    # Behavior
    fallback_scoring: bool
    inmail_enabled: bool


# --- Mode Presets ---

MODE_PRESETS: dict[SearchMode, ModeConfig] = {
    SearchMode.AGGRESSIVE: ModeConfig(
        mode=SearchMode.AGGRESSIVE,
        label="Aggressive",
        description="Need a job THIS week. Maximum applications, lower bar, frequent scans. Auto-applies to external jobs too.",
        interval_minutes=15,
        active_hours_start=7,
        active_hours_end=23,
        max_postings_per_run=200,
        daily_application_limit=150,
        match_threshold=0.55,
        auto_apply_external=True,
        track_external=True,
        fallback_scoring=True,
        inmail_enabled=True,
    ),
    SearchMode.ACTIVE: ModeConfig(
        mode=SearchMode.ACTIVE,
        label="Active",
        description="Actively searching. Balanced pace, good match quality. Notifies for external jobs.",
        interval_minutes=30,
        active_hours_start=9,
        active_hours_end=22,
        max_postings_per_run=100,
        daily_application_limit=80,
        match_threshold=0.70,
        auto_apply_external=False,
        track_external=True,
        fallback_scoring=True,
        inmail_enabled=True,
    ),
    SearchMode.PASSIVE: ModeConfig(
        mode=SearchMode.PASSIVE,
        label="Passive",
        description="Open to opportunities but not in a rush. Only applies to great matches.",
        interval_minutes=120,
        active_hours_start=10,
        active_hours_end=20,
        max_postings_per_run=30,
        daily_application_limit=20,
        match_threshold=0.85,
        auto_apply_external=False,
        track_external=True,
        fallback_scoring=True,
        inmail_enabled=False,
    ),
}


def get_mode_config(mode: SearchMode | str) -> ModeConfig:
    """Get the configuration preset for a search mode."""
    if isinstance(mode, str):
        mode = SearchMode(mode.lower())
    return MODE_PRESETS[mode]


def apply_mode_to_config(mode: SearchMode | str, config_dict: dict) -> dict:
    """Apply a mode preset over an existing config dict.
    
    Returns updated config_dict with mode settings applied.
    Does NOT override: keywords, locations, candidate info, secrets.
    Only overrides: timing, volume, threshold, behavior flags.
    """
    preset = get_mode_config(mode)
    
    if 'scheduler' not in config_dict:
        config_dict['scheduler'] = {}
    config_dict['scheduler']['interval_minutes'] = preset.interval_minutes
    config_dict['scheduler']['active_hours_start'] = preset.active_hours_start
    config_dict['scheduler']['active_hours_end'] = preset.active_hours_end
    
    if 'job_search' not in config_dict:
        config_dict['job_search'] = {}
    config_dict['job_search']['max_postings_per_run'] = preset.max_postings_per_run
    config_dict['job_search']['daily_application_limit'] = preset.daily_application_limit
    config_dict['job_search']['match_threshold'] = preset.match_threshold
    config_dict['job_search']['fallback_scoring'] = preset.fallback_scoring
    config_dict['job_search']['track_external_apply'] = preset.track_external
    config_dict['job_search']['auto_apply_external'] = preset.auto_apply_external
    
    if 'inmail' not in config_dict:
        config_dict['inmail'] = {}
    config_dict['inmail']['enabled'] = preset.inmail_enabled
    
    return config_dict


def get_all_modes() -> list[dict]:
    """Return all modes as dicts (for API/UI consumption)."""
    return [
        {
            "mode": preset.mode.value,
            "label": preset.label,
            "description": preset.description,
            "interval_minutes": preset.interval_minutes,
            "max_postings_per_run": preset.max_postings_per_run,
            "daily_application_limit": preset.daily_application_limit,
            "match_threshold": int(preset.match_threshold * 100),
            "auto_apply_external": preset.auto_apply_external,
        }
        for preset in MODE_PRESETS.values()
    ]

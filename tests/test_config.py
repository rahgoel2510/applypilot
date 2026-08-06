"""Tests for the configuration module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from linkedin_agent.config import (
    ConfigError,
    Settings,
    _build_settings,
    _normalize_threshold,
    get_config,
    reset_config,
)


class TestNormalizeThreshold:
    """Tests for threshold normalization."""

    def test_already_normalized(self):
        assert _normalize_threshold(0.7) == 0.7
        assert _normalize_threshold(0.85) == 0.85
        assert _normalize_threshold(1.0) == 1.0

    def test_integer_percentage(self):
        assert _normalize_threshold(70) == 0.7
        assert _normalize_threshold(85) == 0.85
        assert _normalize_threshold(100) == 1.0

    def test_zero(self):
        assert _normalize_threshold(0.0) == 0.0

    def test_boundary(self):
        assert _normalize_threshold(1.0) == 1.0
        assert _normalize_threshold(1.1) == pytest.approx(0.011)


class TestBuildSettings:
    """Tests for building Settings from YAML data."""

    def test_empty_yaml(self):
        settings = _build_settings({})
        assert settings.candidate.name == ""
        # Active mode defaults apply (threshold=0.70, interval=30)
        assert settings.job_search.match_threshold == 0.7
        assert settings.scheduler.interval_minutes == 30

    def test_candidate_config(self):
        yaml_data = {
            "candidate": {
                "name": "Test User",
                "email": "test@example.com",
                "skills": ["python", "aws"],
            }
        }
        settings = _build_settings(yaml_data)
        assert settings.candidate.name == "Test User"
        assert settings.candidate.email == "test@example.com"
        assert "python" in settings.candidate.skills

    def test_job_search_config(self):
        yaml_data = {
            "job_search": {
                "keywords": ["Senior Engineer", "Staff Engineer"],
                "locations": ["Remote", "SF"],
                "match_threshold": 0.75,
                "max_postings_per_run": 100,
                "search_mode": "custom",
            }
        }
        settings = _build_settings(yaml_data)
        assert settings.job_search.keywords == ["Senior Engineer", "Staff Engineer"]
        assert settings.job_search.locations == ["Remote", "SF"]
        assert settings.job_search.match_threshold == 0.75
        assert settings.job_search.max_postings_per_run == 100

    def test_scheduler_config(self):
        yaml_data = {
            "job_search": {"search_mode": "custom"},
            "scheduler": {
                "interval_minutes": 45,
                "active_hours_start": 8,
                "active_hours_end": 20,
            }
        }
        settings = _build_settings(yaml_data)
        assert settings.scheduler.interval_minutes == 45
        assert settings.scheduler.active_hours_start == 8
        assert settings.scheduler.active_hours_end == 20

    def test_telegram_from_env(self):
        settings = _build_settings({})
        # These come from the env vars set in conftest
        assert settings.telegram.bot_token != ""
        assert settings.telegram.chat_id != ""

    def test_inmail_config(self):
        yaml_data = {"inmail": {"enabled": False, "tone": "casual", "max_length": 200}}
        settings = _build_settings(yaml_data)
        assert settings.inmail.enabled is False
        assert settings.inmail.tone == "casual"
        assert settings.inmail.max_length == 200

    def test_self_learning_config(self):
        yaml_data = {
            "self_learning": {
                "target_companies": ["Google", "Meta"],
                "blocklist_companies": ["Scam Inc"],
                "target_boost": 0.2,
                "blocklist_penalty": 0.3,
            }
        }
        settings = _build_settings(yaml_data)
        assert "Google" in settings.self_learning.target_companies
        assert "Scam Inc" in settings.self_learning.blocklist_companies
        assert settings.self_learning.target_boost == 0.2

    def test_threshold_normalization_in_build(self):
        yaml_data = {"job_search": {"match_threshold": 70, "search_mode": "custom"}}
        settings = _build_settings(yaml_data)
        assert settings.job_search.match_threshold == 0.7

    def test_search_mode_active_applies_defaults(self):
        yaml_data = {"job_search": {"search_mode": "active"}}
        settings = _build_settings(yaml_data)
        assert settings.job_search.match_threshold == 0.70
        assert settings.job_search.daily_application_limit == 80

    def test_search_mode_aggressive(self):
        yaml_data = {"job_search": {"search_mode": "aggressive"}}
        settings = _build_settings(yaml_data)
        assert settings.job_search.match_threshold == 0.55
        assert settings.job_search.daily_application_limit == 150


class TestGetConfig:
    """Tests for the config singleton accessor."""

    def test_returns_settings(self):
        config = get_config(validate=False, reload=True)
        assert isinstance(config, Settings)

    def test_singleton_behavior(self):
        c1 = get_config(validate=False, reload=True)
        c2 = get_config(validate=False)
        assert c1 is c2

    def test_reload_returns_fresh(self):
        c1 = get_config(validate=False, reload=True)
        c2 = get_config(validate=False, reload=True)
        # Not the same object when reloaded
        assert c1 is not c2

    def test_validation_raises_on_missing_vars(self, monkeypatch):
        """Missing env vars no longer crash — settings can come from DB instead.
        
        _validate_env() now logs a warning instead of raising ConfigError.
        get_config() should succeed and return a Settings object with defaults.
        """
        # Clear all required env vars AND prevent .env from reloading them
        required = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "OPENAI_API_KEY",
                    "LINKEDIN_EMAIL", "LINKEDIN_PASSWORD"]
        for var in required:
            monkeypatch.delenv(var, raising=False)

        # Patch load_dotenv to prevent it from re-reading .env file
        with patch("linkedin_agent.config.load_dotenv"):
            reset_config()
            # Should NOT raise — just returns settings with empty credential fields
            settings = get_config(validate=True, reload=True)
            assert settings is not None


class TestSettingsImmutability:
    """Verify Settings and sub-configs are frozen dataclasses."""

    def test_settings_is_frozen(self):
        config = get_config(validate=False, reload=True)
        with pytest.raises(Exception):
            config.openai_api_key = "hacked"

    def test_candidate_is_frozen(self):
        config = get_config(validate=False, reload=True)
        with pytest.raises(Exception):
            config.candidate.name = "hacked"

    def test_job_search_is_frozen(self):
        config = get_config(validate=False, reload=True)
        with pytest.raises(Exception):
            config.job_search.match_threshold = 0.0

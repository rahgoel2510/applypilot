"""Unit tests for linkedin_agent.config module."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from linkedin_agent.config import (
    ConfigError,
    Settings,
    CandidateConfig,
    JobSearchConfig,
    SchedulerConfig,
    TelegramConfig,
    InmailConfig,
    _build_settings,
    _load_yaml,
    _validate_env,
    get_config,
    reset_config,
    REQUIRED_ENV_VARS,
)


# ===========================================================================
# YAML loading
# ===========================================================================


class TestYamlLoading:
    """Tests for _load_yaml helper."""

    def test_load_valid_yaml(self, config_yaml_file):
        data = _load_yaml(config_yaml_file)
        assert data["candidate"]["name"] == "Test User"
        assert data["job_search"]["match_threshold"] == 0.75

    def test_load_missing_file(self, tmp_path):
        """Missing file returns empty dict, not an error."""
        data = _load_yaml(tmp_path / "nonexistent.yaml")
        assert data == {}

    def test_load_empty_file(self, tmp_path):
        """Empty YAML file returns empty dict."""
        empty = tmp_path / "empty.yaml"
        empty.write_text("")
        data = _load_yaml(empty)
        assert data == {}

    def test_load_non_dict_yaml(self, tmp_path):
        """YAML that parses to a non-dict (e.g., list) returns empty dict."""
        list_yaml = tmp_path / "list.yaml"
        list_yaml.write_text("- item1\n- item2\n")
        data = _load_yaml(list_yaml)
        assert data == {}


# ===========================================================================
# Environment validation
# ===========================================================================


class TestEnvValidation:
    """Tests for _validate_env."""

    def test_all_vars_present(self, monkeypatch):
        """No error when all required vars are set."""
        for var in REQUIRED_ENV_VARS:
            monkeypatch.setenv(var, "test-value")
        # Should not raise
        _validate_env()

    def test_missing_single_var(self, monkeypatch):
        """Raises ConfigError listing the missing variable."""
        for var in REQUIRED_ENV_VARS:
            monkeypatch.setenv(var, "test-value")
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN")

        with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
            _validate_env()

    def test_missing_multiple_vars(self, monkeypatch):
        """Raises ConfigError listing all missing variables."""
        # Clear all required vars
        for var in REQUIRED_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

        with pytest.raises(ConfigError) as exc_info:
            _validate_env()

        for var in REQUIRED_ENV_VARS:
            assert var in str(exc_info.value)


# ===========================================================================
# Settings construction
# ===========================================================================


class TestBuildSettings:
    """Tests for _build_settings."""

    def test_builds_from_yaml_data(self, monkeypatch):
        """Settings are correctly built from YAML dict + env vars."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok-123")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat-456")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("LINKEDIN_EMAIL", "user@test.com")
        monkeypatch.setenv("LINKEDIN_PASSWORD", "pass123")

        yaml_data = {
            "candidate": {
                "name": "Test User",
                "email": "test@example.com",
                "notice_period": "60 days",
                "preferred_cities": ["Delhi"],
            },
            "job_search": {
                "match_threshold": 0.90,
                "max_postings_per_run": 25,
            },
            "scheduler": {
                "interval_minutes": 45,
                "active_hours_start": 8,
                "active_hours_end": 21,
            },
            "telegram": {
                "notify_on_submit": False,
            },
            "inmail": {
                "enabled": False,
                "tone": "casual",
            },
        }

        settings = _build_settings(yaml_data)

        assert settings.candidate.name == "Test User"
        assert settings.candidate.notice_period == "60 days"
        assert settings.candidate.preferred_cities == ["Delhi"]
        assert settings.job_search.match_threshold == 0.90
        assert settings.job_search.max_postings_per_run == 25
        assert settings.scheduler.interval_minutes == 45
        assert settings.telegram.bot_token == "tok-123"
        assert settings.telegram.notify_on_submit is False
        assert settings.inmail.enabled is False
        assert settings.inmail.tone == "casual"
        assert settings.openai_api_key == "sk-test"
        assert settings.linkedin_email == "user@test.com"

    def test_defaults_when_yaml_empty(self, monkeypatch):
        """Default values are used when YAML is empty."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "cid")
        monkeypatch.setenv("OPENAI_API_KEY", "sk")
        monkeypatch.setenv("LINKEDIN_EMAIL", "e")
        monkeypatch.setenv("LINKEDIN_PASSWORD", "p")

        settings = _build_settings({})

        assert settings.candidate.name == ""
        # Active mode defaults: threshold=0.70, max_postings=100, interval=30
        assert settings.job_search.match_threshold == 0.70
        assert settings.job_search.max_postings_per_run == 100
        assert settings.scheduler.interval_minutes == 30
        assert settings.inmail.enabled is True
        assert settings.inmail.max_length == 300

    def test_env_overrides_yaml_for_threshold(self, monkeypatch):
        """MATCH_THRESHOLD env var overrides yaml value."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.setenv("LINKEDIN_EMAIL", "e")
        monkeypatch.setenv("LINKEDIN_PASSWORD", "p")
        monkeypatch.setenv("MATCH_THRESHOLD", "0.95")

        yaml_data = {"job_search": {"match_threshold": 0.70}}
        settings = _build_settings(yaml_data)
        assert settings.job_search.match_threshold == 0.95


# ===========================================================================
# Singleton get_config
# ===========================================================================


class TestGetConfig:
    """Tests for the get_config singleton accessor."""

    def test_get_config_no_validate(self, monkeypatch, config_yaml_file):
        """get_config(validate=False) loads even without env vars."""
        # Patch the module-level paths
        monkeypatch.setattr("linkedin_agent.config.CONFIG_FILE", config_yaml_file)
        monkeypatch.setattr("linkedin_agent.config.ENV_FILE", config_yaml_file.parent / ".env")

        settings = get_config(validate=False, reload=True)
        assert settings.candidate.name == "Test User"
        assert settings.job_search.match_threshold == 0.75

    def test_get_config_validate_raises_without_env(self, monkeypatch, config_yaml_file):
        """get_config(validate=True) raises when required vars are missing."""
        monkeypatch.setattr("linkedin_agent.config.CONFIG_FILE", config_yaml_file)
        monkeypatch.setattr("linkedin_agent.config.ENV_FILE", config_yaml_file.parent / ".env")
        for var in REQUIRED_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

        with pytest.raises(ConfigError):
            get_config(validate=True, reload=True)

    def test_singleton_caching(self, monkeypatch, config_yaml_file):
        """Second call returns same instance without reload."""
        monkeypatch.setattr("linkedin_agent.config.CONFIG_FILE", config_yaml_file)
        monkeypatch.setattr("linkedin_agent.config.ENV_FILE", config_yaml_file.parent / ".env")

        s1 = get_config(validate=False, reload=True)
        s2 = get_config(validate=False)
        assert s1 is s2

    def test_reload_forces_fresh_load(self, monkeypatch, config_yaml_file):
        """reload=True creates a new instance."""
        monkeypatch.setattr("linkedin_agent.config.CONFIG_FILE", config_yaml_file)
        monkeypatch.setattr("linkedin_agent.config.ENV_FILE", config_yaml_file.parent / ".env")

        s1 = get_config(validate=False, reload=True)
        s2 = get_config(validate=False, reload=True)
        # Both have same values but are different objects
        assert s1.candidate.name == s2.candidate.name


# ===========================================================================
# Dataclass defaults
# ===========================================================================


class TestDataclassDefaults:
    """Verify default values on config dataclasses."""

    def test_candidate_defaults(self):
        c = CandidateConfig()
        assert c.name == ""
        assert c.resume_filename == "resume.pdf"
        assert c.notice_period == "Immediate"
        assert c.willing_to_relocate is True
        assert c.preferred_cities == []

    def test_job_search_defaults(self):
        js = JobSearchConfig()
        assert js.match_threshold == 0.80
        assert js.max_postings_per_run == 50
        assert js.collection == "Recommended"
        assert js.skip_external_apply is False
        assert js.track_external_apply is True

    def test_scheduler_defaults(self):
        sc = SchedulerConfig()
        assert sc.interval_minutes == 60
        assert sc.active_hours_start == 9
        assert sc.active_hours_end == 22

    def test_telegram_defaults(self):
        tg = TelegramConfig()
        assert tg.bot_token == ""
        assert tg.notify_on_submit is True
        assert tg.notify_on_skip is False

    def test_inmail_defaults(self):
        im = InmailConfig()
        assert im.enabled is True
        assert im.tone == "professional"
        assert im.max_length == 300

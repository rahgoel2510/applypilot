"""Tests for search_modes module."""

import pytest

from linkedin_agent.search_modes import (
    ModeConfig,
    SearchMode,
    apply_mode_to_config,
    get_all_modes,
    get_mode_config,
)


class TestGetModeConfig:
    """Tests for retrieving mode presets."""

    def test_get_aggressive(self):
        config = get_mode_config("aggressive")
        assert isinstance(config, ModeConfig)
        assert config.mode == SearchMode.AGGRESSIVE
        assert config.match_threshold == 0.55
        assert config.daily_application_limit == 150
        assert config.interval_minutes == 15
        assert config.auto_apply_external is True

    def test_get_active(self):
        config = get_mode_config("active")
        assert config.mode == SearchMode.ACTIVE
        assert config.match_threshold == 0.70
        assert config.daily_application_limit == 80
        assert config.interval_minutes == 30

    def test_get_passive(self):
        config = get_mode_config("passive")
        assert config.mode == SearchMode.PASSIVE
        assert config.match_threshold == 0.85
        assert config.daily_application_limit == 20
        assert config.interval_minutes == 120
        assert config.inmail_enabled is False

    def test_get_by_enum(self):
        config = get_mode_config(SearchMode.AGGRESSIVE)
        assert config.mode == SearchMode.AGGRESSIVE

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            get_mode_config("nonexistent")


class TestApplyModeToConfig:
    """Tests for applying mode presets to config dict."""

    def test_applies_scheduler_settings(self):
        config_dict = {}
        result = apply_mode_to_config("aggressive", config_dict)
        assert result["scheduler"]["interval_minutes"] == 15
        assert result["scheduler"]["active_hours_start"] == 7
        assert result["scheduler"]["active_hours_end"] == 23

    def test_applies_job_search_settings(self):
        config_dict = {}
        result = apply_mode_to_config("passive", config_dict)
        assert result["job_search"]["match_threshold"] == 0.85
        assert result["job_search"]["daily_application_limit"] == 20
        assert result["job_search"]["max_postings_per_run"] == 30

    def test_applies_inmail_settings(self):
        config_dict = {}
        result = apply_mode_to_config("passive", config_dict)
        assert result["inmail"]["enabled"] is False

    def test_preserves_existing_keys(self):
        config_dict = {"custom_key": "preserved"}
        result = apply_mode_to_config("active", config_dict)
        assert result["custom_key"] == "preserved"


class TestGetAllModes:
    """Tests for listing all modes."""

    def test_returns_all_three(self):
        modes = get_all_modes()
        assert len(modes) == 3

    def test_mode_structure(self):
        modes = get_all_modes()
        for mode in modes:
            assert "mode" in mode
            assert "label" in mode
            assert "description" in mode
            assert "interval_minutes" in mode
            assert "match_threshold" in mode

    def test_threshold_is_percentage(self):
        """UI expects integer percentage, not float."""
        modes = get_all_modes()
        for mode in modes:
            assert mode["match_threshold"] >= 50
            assert mode["match_threshold"] <= 100


class TestModeConfigFrozen:
    """Verify ModeConfig is immutable."""

    def test_frozen(self):
        config = get_mode_config("active")
        with pytest.raises(Exception):
            config.match_threshold = 0.0

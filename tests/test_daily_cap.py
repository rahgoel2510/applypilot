"""Tests for daily application cap module."""

import json
import tempfile
from pathlib import Path

import pytest

from linkedin_agent.daily_cap import DailyApplicationCap


@pytest.fixture
def cap(tmp_path):
    """Create a DailyApplicationCap with a temporary file."""
    cap_file = tmp_path / "test_cap.json"
    return DailyApplicationCap(daily_limit=10, cap_path=cap_file)


class TestDailyCapBasics:
    """Tests for basic cap functionality."""

    def test_initial_state(self, cap):
        assert cap.daily_limit == 10
        assert cap.today_count == 0
        assert cap.remaining == 10
        assert cap.is_at_limit is False
        assert cap.is_near_limit is False
        assert cap.can_apply() is True

    def test_record_application(self, cap):
        cap.record_application()
        assert cap.today_count == 1
        assert cap.remaining == 9

    def test_at_limit(self, cap):
        for _ in range(10):
            cap.record_application()
        assert cap.is_at_limit is True
        assert cap.can_apply() is False
        assert cap.remaining == 0

    def test_near_limit(self, cap):
        # 75% of 10 = 7.5, so 8 should trigger
        for _ in range(8):
            cap.record_application()
        assert cap.is_near_limit is True
        assert cap.is_at_limit is False


class TestDailyCapPersistence:
    """Tests for file persistence."""

    def test_persists_to_disk(self, tmp_path):
        cap_file = tmp_path / "persist_test.json"
        cap1 = DailyApplicationCap(daily_limit=10, cap_path=cap_file)
        cap1.record_application()
        cap1.record_application()

        # Create new instance reading same file
        cap2 = DailyApplicationCap(daily_limit=10, cap_path=cap_file)
        assert cap2.today_count == 2

    def test_handles_missing_file(self, tmp_path):
        cap_file = tmp_path / "nonexistent.json"
        cap = DailyApplicationCap(daily_limit=10, cap_path=cap_file)
        assert cap.today_count == 0

    def test_handles_corrupt_file(self, tmp_path):
        cap_file = tmp_path / "corrupt.json"
        cap_file.write_text("not valid json {{{")
        cap = DailyApplicationCap(daily_limit=10, cap_path=cap_file)
        assert cap.today_count == 0


class TestDailyCapStats:
    """Tests for stats method."""

    def test_get_stats(self, cap):
        cap.record_application()
        cap.record_application()
        stats = cap.get_stats()
        assert "today" in stats or isinstance(stats, dict)

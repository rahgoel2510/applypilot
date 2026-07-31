"""Tests for daily application cap tracking."""

import json
import tempfile
from pathlib import Path

import pytest

from linkedin_agent.daily_cap import DailyApplicationCap


@pytest.fixture
def tmp_cap_path(tmp_path):
    """Provide a temporary file path for cap persistence."""
    return tmp_path / "daily_applications.json"


@pytest.fixture
def cap(tmp_cap_path):
    """Create a DailyApplicationCap instance with a temp file."""
    return DailyApplicationCap(daily_limit=5, cap_path=tmp_cap_path)


class TestDailyApplicationCap:
    """Test suite for DailyApplicationCap."""

    def test_initial_count_is_zero(self, cap):
        """Fresh instance should have zero applications today."""
        assert cap.today_count == 0
        assert cap.remaining == 5
        assert cap.is_at_limit is False
        assert cap.is_near_limit is False
        assert cap.can_apply() is True

    def test_record_application_increments(self, cap):
        """Each record_application call should increment today_count."""
        cap.record_application()
        assert cap.today_count == 1

        cap.record_application()
        assert cap.today_count == 2

        cap.record_application()
        assert cap.today_count == 3

    def test_is_at_limit_when_count_reaches_limit(self, cap):
        """is_at_limit should be True when count >= daily_limit."""
        # Record up to the limit (5)
        for _ in range(5):
            cap.record_application()

        assert cap.today_count == 5
        assert cap.is_at_limit is True
        assert cap.can_apply() is False
        assert cap.remaining == 0

    def test_remaining_calculation(self, cap):
        """remaining should correctly track how many applications are left."""
        assert cap.remaining == 5

        cap.record_application()
        assert cap.remaining == 4

        cap.record_application()
        assert cap.remaining == 3

        # Record the rest
        for _ in range(3):
            cap.record_application()
        assert cap.remaining == 0

        # Even if somehow we go over, remaining stays at 0
        cap.record_application()
        assert cap.remaining == 0

    def test_persistence_to_disk(self, tmp_cap_path):
        """Data should survive instance recreation (loaded from disk)."""
        # Create first instance and record some applications
        cap1 = DailyApplicationCap(daily_limit=10, cap_path=tmp_cap_path)
        cap1.record_application()
        cap1.record_application()
        cap1.record_application()
        assert cap1.today_count == 3

        # Create a new instance pointing to the same file
        cap2 = DailyApplicationCap(daily_limit=10, cap_path=tmp_cap_path)
        assert cap2.today_count == 3

        # Record more on the second instance
        cap2.record_application()
        assert cap2.today_count == 4

        # Verify the file exists and contains valid JSON
        assert tmp_cap_path.exists()
        data = json.loads(tmp_cap_path.read_text())
        assert isinstance(data, dict)

    def test_is_near_limit_threshold(self, tmp_cap_path):
        """is_near_limit should trigger at 75% of the daily limit."""
        cap = DailyApplicationCap(daily_limit=8, cap_path=tmp_cap_path)

        # 75% of 8 = 6 → near limit at count >= 6
        for _ in range(5):
            cap.record_application()
        assert cap.is_near_limit is False

        cap.record_application()  # 6th application
        assert cap.is_near_limit is True

    def test_get_stats_returns_correct_dict(self, cap):
        """get_stats should return a dictionary with all expected keys."""
        cap.record_application()
        cap.record_application()

        stats = cap.get_stats()
        assert stats["today_count"] == 2
        assert stats["daily_limit"] == 5
        assert stats["remaining"] == 3
        assert stats["at_limit"] is False
        assert stats["near_limit"] is False

    def test_handles_corrupt_file(self, tmp_cap_path):
        """Should handle corrupted JSON gracefully."""
        # Write invalid JSON
        tmp_cap_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_cap_path.write_text("not valid json {{{")

        # Should not raise, starts with empty data
        cap = DailyApplicationCap(daily_limit=5, cap_path=tmp_cap_path)
        assert cap.today_count == 0
        assert cap.can_apply() is True

    def test_handles_missing_file(self, tmp_path):
        """Should handle missing file gracefully."""
        missing_path = tmp_path / "nonexistent" / "daily_applications.json"
        cap = DailyApplicationCap(daily_limit=5, cap_path=missing_path)
        assert cap.today_count == 0

        # Should create parent directories on first write
        cap.record_application()
        assert missing_path.exists()

    def test_daily_limit_property(self, cap):
        """daily_limit property should return the configured limit."""
        assert cap.daily_limit == 5

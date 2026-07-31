"""Daily application cap tracking to avoid LinkedIn rate limiting.

Tracks applications submitted today and stops the agent when approaching
LinkedIn's soft daily limit. Persists to disk to survive restarts.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CAP_PATH = Path.home() / ".linkedin_agent" / "daily_applications.json"
DEFAULT_DAILY_LIMIT = 80  # Conservative limit (LinkedIn soft cap is ~100)
WARNING_THRESHOLD = 0.75  # Warn at 75% of limit


class DailyApplicationCap:
    """Tracks daily application count and enforces a configurable cap."""

    def __init__(
        self,
        daily_limit: int = DEFAULT_DAILY_LIMIT,
        cap_path: str | Path | None = None,
    ) -> None:
        self._limit = daily_limit
        self._path = Path(cap_path) if cap_path else DEFAULT_CAP_PATH
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._load()

    @property
    def daily_limit(self) -> int:
        return self._limit

    @property
    def today_count(self) -> int:
        """Number of applications submitted today."""
        with self._lock:
            today = date.today().isoformat()
            return self._data.get(today, {}).get("count", 0)

    @property
    def remaining(self) -> int:
        """Number of applications remaining before hitting the daily cap."""
        return max(0, self._limit - self.today_count)

    @property
    def is_at_limit(self) -> bool:
        """True if the daily cap has been reached."""
        return self.today_count >= self._limit

    @property
    def is_near_limit(self) -> bool:
        """True if approaching the limit (past warning threshold)."""
        return self.today_count >= int(self._limit * WARNING_THRESHOLD)

    def record_application(self) -> None:
        """Record one application submission for today."""
        with self._lock:
            today = date.today().isoformat()
            if today not in self._data:
                self._data[today] = {"count": 0, "timestamps": []}
            self._data[today]["count"] += 1
            self._data[today]["timestamps"].append(
                datetime.now().isoformat()
            )
            self._cleanup_old_days()
            self._save()

    def can_apply(self) -> bool:
        """Check if another application is allowed today."""
        return not self.is_at_limit

    def get_stats(self) -> dict[str, Any]:
        """Return current daily stats."""
        return {
            "today_count": self.today_count,
            "daily_limit": self._limit,
            "remaining": self.remaining,
            "at_limit": self.is_at_limit,
            "near_limit": self.is_near_limit,
        }

    def _cleanup_old_days(self) -> None:
        """Remove entries older than 7 days to keep file small."""
        cutoff = date.today().toordinal() - 7
        to_remove = [
            day for day in self._data
            if self._safe_parse_date(day) and date.fromisoformat(day).toordinal() < cutoff
        ]
        for day in to_remove:
            del self._data[day]

    @staticmethod
    def _safe_parse_date(s: str) -> bool:
        try:
            date.fromisoformat(s)
            return True
        except (ValueError, TypeError):
            return False

    def _load(self) -> None:
        if not self._path.exists():
            self._data = {}
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            if not isinstance(self._data, dict):
                self._data = {}
        except (json.JSONDecodeError, OSError):
            self._data = {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            tmp.replace(self._path)
        except OSError as exc:
            logger.error(f"Failed to save daily cap data: {exc}")


# Singleton
_cap: DailyApplicationCap | None = None


def get_daily_cap(daily_limit: int = DEFAULT_DAILY_LIMIT) -> DailyApplicationCap:
    global _cap
    if _cap is None:
        _cap = DailyApplicationCap(daily_limit=daily_limit)
    return _cap

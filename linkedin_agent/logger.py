"""Logging and reporting module for LinkedIn Job Agent.

Provides:
- ApplicationLogger: 4-bucket tally tracker (submitted, paused, skipped_threshold, skipped_external)
- Configured Python logging with rotating file handler and Rich console output
- Thread-safe operation
- Function timing decorator
"""

from __future__ import annotations

import csv
import functools
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOG_DIR = Path.home() / ".linkedin_agent" / "logs"
LOG_FILE = LOG_DIR / "agent.log"
MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class ResultStatus(str, Enum):
    """Possible outcomes of a job application attempt."""

    SUBMITTED = "submitted"
    PAUSED = "paused"
    SKIPPED_THRESHOLD = "skipped_threshold"
    SKIPPED_EXTERNAL = "skipped_external"


@dataclass
class ApplicationResult:
    """Represents the outcome of processing a single job posting."""

    status: ResultStatus
    company: str
    title: str
    location: str
    match_score: Optional[float] = None
    blocking_fields: Optional[list[str]] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Application Logger (4-bucket tally)
# ---------------------------------------------------------------------------


class ApplicationLogger:
    """Thread-safe session logger that maintains a 4-bucket running tally.

    Buckets:
        submitted         - successfully applied jobs
        paused            - jobs paused due to blocking/manual fields
        skipped_threshold - jobs skipped because match_score < threshold
        skipped_external  - jobs skipped because they require external apply
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session_start = datetime.now(timezone.utc).isoformat()
        self._buckets: dict[str, list[dict[str, Any]]] = {
            "submitted": [],
            "paused": [],
            "skipped_threshold": [],
            "skipped_external": [],
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_result(self, result: ApplicationResult) -> None:
        """Add a result to the appropriate bucket (thread-safe)."""
        entry = self._result_to_entry(result)
        with self._lock:
            self._buckets[result.status.value].append(entry)

    def get_tally(self) -> dict[str, Any]:
        """Return counts and details for each bucket."""
        with self._lock:
            return {
                bucket: {
                    "count": len(entries),
                    "details": list(entries),
                }
                for bucket, entries in self._buckets.items()
            }

    def get_tally_summary(self) -> str:
        """Return a formatted text summary suitable for Telegram messages."""
        with self._lock:
            counts = {b: len(e) for b, e in self._buckets.items()}
            total = sum(counts.values())

        lines = [
            "📊 *Session Tally*",
            f"━━━━━━━━━━━━━━━━━━",
            f"✅ Submitted: {counts['submitted']}",
            f"⏸️ Paused: {counts['paused']}",
            f"⬇️ Below threshold: {counts['skipped_threshold']}",
            f"🔗 External apply: {counts['skipped_external']}",
            f"━━━━━━━━━━━━━━━━━━",
            f"📦 Total processed: {total}",
        ]

        if total > 0:
            success_rate = (counts["submitted"] / total) * 100
            lines.append(f"🎯 Success rate: {success_rate:.1f}%")

        return "\n".join(lines)

    def get_session_stats(self) -> dict[str, Any]:
        """Return aggregated session statistics."""
        with self._lock:
            counts = {b: len(e) for b, e in self._buckets.items()}
            total = sum(counts.values())
            submitted = counts["submitted"]

            # Average match score for submitted jobs
            submitted_scores = [
                entry["match_score"]
                for entry in self._buckets["submitted"]
                if entry.get("match_score") is not None
            ]
            avg_score = (
                sum(submitted_scores) / len(submitted_scores)
                if submitted_scores
                else None
            )

        return {
            "session_start": self._session_start,
            "total_processed": total,
            "submitted": submitted,
            "paused": counts["paused"],
            "skipped_threshold": counts["skipped_threshold"],
            "skipped_external": counts["skipped_external"],
            "success_rate": (submitted / total * 100) if total > 0 else 0.0,
            "avg_match_score_submitted": avg_score,
        }

    def save_to_file(self) -> Path:
        """Persist session data to ~/.linkedin_agent/logs/session_{date}.json.

        Returns the path to the saved file.
        """
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        filepath = LOG_DIR / f"session_{date_str}.json"

        with self._lock:
            payload = {
                "session_start": self._session_start,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "stats": self.get_session_stats(),
                "buckets": {b: list(e) for b, e in self._buckets.items()},
            }

        # Release lock before I/O
        filepath.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return filepath

    @staticmethod
    def load_session(date: str) -> dict[str, Any]:
        """Load a previous session by date prefix (e.g. '2026-07-27').

        Searches for session files matching the given date string.
        Returns the parsed JSON content of the most recent matching file.

        Raises:
            FileNotFoundError: If no session file matches the given date.
        """
        if not LOG_DIR.exists():
            raise FileNotFoundError(f"Log directory does not exist: {LOG_DIR}")

        matches = sorted(LOG_DIR.glob(f"session_{date}*.json"))
        if not matches:
            raise FileNotFoundError(
                f"No session files found matching date '{date}' in {LOG_DIR}"
            )

        # Return the most recent match
        latest = matches[-1]
        return json.loads(latest.read_text(encoding="utf-8"))

    def export_csv(self, filepath: str) -> None:
        """Export all results as a flat CSV file.

        Columns: status, company, title, location, match_score, blocking_fields, timestamp
        """
        csv_path = Path(filepath)
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "status",
            "company",
            "title",
            "location",
            "match_score",
            "blocking_fields",
            "timestamp",
        ]

        with self._lock:
            rows: list[dict[str, Any]] = []
            for bucket_name, entries in self._buckets.items():
                for entry in entries:
                    row = {
                        "status": bucket_name,
                        "company": entry.get("company", ""),
                        "title": entry.get("title", ""),
                        "location": entry.get("location", ""),
                        "match_score": entry.get("match_score", ""),
                        "blocking_fields": (
                            "; ".join(entry["blocking_fields"])
                            if entry.get("blocking_fields")
                            else ""
                        ),
                        "timestamp": entry.get("timestamp", ""),
                    }
                    rows.append(row)

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # ------------------------------------------------------------------
    # Rich console display
    # ------------------------------------------------------------------

    def print_tally(self, console: Optional[Console] = None) -> None:
        """Print a rich-formatted tally table to the console."""
        console = console or Console()
        table = Table(title="Session Tally", show_lines=True)
        table.add_column("Bucket", style="bold cyan")
        table.add_column("Count", justify="right", style="bold green")

        with self._lock:
            for bucket, entries in self._buckets.items():
                table.add_row(bucket.replace("_", " ").title(), str(len(entries)))

        console.print(table)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _result_to_entry(result: ApplicationResult) -> dict[str, Any]:
        """Convert an ApplicationResult to a bucket entry dict."""
        entry: dict[str, Any] = {
            "company": result.company,
            "title": result.title,
            "location": result.location,
            "timestamp": result.timestamp,
        }

        if result.status in (ResultStatus.SUBMITTED, ResultStatus.SKIPPED_THRESHOLD):
            entry["match_score"] = result.match_score

        if result.status == ResultStatus.PAUSED:
            entry["blocking_fields"] = result.blocking_fields or []

        return entry


# ---------------------------------------------------------------------------
# Timing decorator
# ---------------------------------------------------------------------------


def timed(logger: Optional[logging.Logger] = None) -> Callable:
    """Decorator that logs the execution time of a function.

    Usage:
        @timed()
        def my_function():
            ...

        @timed(logger=custom_logger)
        async def my_async_function():
            ...
    """

    def decorator(func: Callable) -> Callable:
        _logger = logger or logging.getLogger(func.__module__)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.perf_counter() - start
                _logger.debug(
                    "%s completed in %.3fs", func.__qualname__, elapsed
                )

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            import asyncio

            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed = time.perf_counter() - start
                _logger.debug(
                    "%s completed in %.3fs", func.__qualname__, elapsed
                )

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# Python logging configuration
# ---------------------------------------------------------------------------


def setup_logging(
    level: str = "INFO",
    console_level: Optional[str] = None,
    file_level: Optional[str] = None,
) -> logging.Logger:
    """Configure the root logger with Rich console handler and rotating file handler.

    Args:
        level: Default log level (used if console_level/file_level not specified).
        console_level: Override log level for console output.
        file_level: Override log level for file output.

    Returns:
        The configured root logger for the linkedin_agent package.
    """
    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Get or create the package-level logger
    root_logger = logging.getLogger("linkedin_agent")
    root_logger.setLevel(logging.DEBUG)  # Allow all; handlers filter

    # Avoid duplicate handlers on repeated calls
    root_logger.handlers.clear()

    # --- File handler (rotating) ---
    file_handler = RotatingFileHandler(
        filename=str(LOG_FILE),
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, (file_level or level).upper(), logging.INFO))
    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # --- Console handler (Rich) ---
    rich_handler = RichHandler(
        level=getattr(logging, (console_level or level).upper(), logging.INFO),
        console=Console(stderr=True),
        show_time=True,
        show_path=True,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        markup=True,
    )
    root_logger.addHandler(rich_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the linkedin_agent namespace.

    Usage:
        from linkedin_agent.logger import get_logger
        log = get_logger(__name__)
    """
    return logging.getLogger(f"linkedin_agent.{name}")

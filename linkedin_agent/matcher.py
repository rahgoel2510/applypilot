"""Job matching and decision engine.

Provides the JobMatcher class responsible for:
- Computing match scores (matched skills / required skills)
- Threshold-based go/no-go decisions
- Deduplication against an on-disk applied-jobs set
- Classifying application form fields into auto-fillable vs needs-human-input
- Detecting sensitive fields (CTC, equity, nationality, etc.)

Thread-safe: all mutable state access is protected by a threading.Lock.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Persistence path for deduplication
# ---------------------------------------------------------------------------

APPLIED_FILE: Path = Path.home() / ".linkedin_agent" / "applied.json"

# ---------------------------------------------------------------------------
# Sensitive-field detection patterns
# ---------------------------------------------------------------------------

_CTC_SALARY_PATTERNS: list[str] = [
    "ctc",
    "salary",
    "compensation",
    "package",
    "fixed",
    "variable",
]

_EQUITY_PATTERNS: list[str] = [
    "rsu",
    "equity",
    "stock",
    "esop",
    "vesting",
]

_NATIONALITY_PATTERNS: list[str] = [
    "nationality",
    "citizenship",
    "passport",
    "country of origin",
]

_EXPERIENCE_UNKNOWN_PATTERNS: list[str] = [
    r"years?\s*(of)?\s*experience",
]

# Compile a master regex for quick matching (case-insensitive)
_SENSITIVE_REGEX: re.Pattern[str] = re.compile(
    "|".join(
        _CTC_SALARY_PATTERNS
        + _EQUITY_PATTERNS
        + _NATIONALITY_PATTERNS
        + _EXPERIENCE_UNKNOWN_PATTERNS
    ),
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Auto-fill mapping: profile key -> field detection keywords
# ---------------------------------------------------------------------------

_AUTOFILL_MAP: dict[str, list[str]] = {
    "notice_period": ["notice period", "notice", "joining time", "start date"],
    "willing_to_relocate": ["relocat", "relocation", "willing to move"],
    "work_authorization": [
        "work authorization",
        "authorized to work",
        "visa",
        "sponsorship",
        "work permit",
    ],
    "preferred_cities": [
        "preferred location",
        "preferred city",
        "location preference",
        "city",
        "where would you like to work",
    ],
}

# Pre-compile per-key patterns for efficient matching
_AUTOFILL_PATTERNS: dict[str, re.Pattern[str]] = {
    key: re.compile("|".join(re.escape(kw) for kw in keywords), re.IGNORECASE)
    for key, keywords in _AUTOFILL_MAP.items()
}


# ---------------------------------------------------------------------------
# JobMatcher class
# ---------------------------------------------------------------------------


class JobMatcher:
    """Stateful job matching and decision engine.

    Args:
        threshold: Minimum match score (0.0–1.0) to consider a job worth applying.
                   Defaults to 0.80.
    """

    def __init__(self, threshold: float = 0.80) -> None:
        self._threshold = threshold
        self._lock = threading.Lock()
        self._applied: set[str] = set()
        self._load_applied()

    # ------------------------------------------------------------------
    # Score & threshold
    # ------------------------------------------------------------------

    @staticmethod
    def compute_match_score(matched: int, required: int) -> float:
        """Compute match score as matched / required.

        Returns 0.0 when required is zero or negative to avoid division errors.
        """
        if required <= 0:
            return 0.0
        return min(matched / required, 1.0)

    def meets_threshold(self, score: float) -> bool:
        """Return True if *score* meets or exceeds the configured threshold."""
        return score >= self._threshold

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    @staticmethod
    def _dedup_key(company: str, title: str) -> str:
        """Normalize company+title into a dedup key."""
        return f"{company.strip().lower()}||{title.strip().lower()}"

    def is_duplicate(self, company: str, title: str) -> bool:
        """Check whether we have already applied to this company+title combo."""
        key = self._dedup_key(company, title)
        with self._lock:
            return key in self._applied

    def add_to_applied(self, company: str, title: str) -> None:
        """Record a successful application for future dedup."""
        key = self._dedup_key(company, title)
        with self._lock:
            self._applied.add(key)
            self._persist_applied()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_applied(self) -> None:
        """Load the applied set from disk (thread-safe, called in __init__)."""
        with self._lock:
            if APPLIED_FILE.exists():
                try:
                    data = json.loads(APPLIED_FILE.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        self._applied = set(data)
                except (json.JSONDecodeError, OSError):
                    # Corrupted or unreadable file — start fresh
                    self._applied = set()

    def _persist_applied(self) -> None:
        """Write the applied set to disk. Caller must hold self._lock."""
        APPLIED_FILE.parent.mkdir(parents=True, exist_ok=True)
        APPLIED_FILE.write_text(
            json.dumps(sorted(self._applied), indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Sensitive field detection
    # ------------------------------------------------------------------

    @staticmethod
    def is_sensitive_field(field_name: str) -> bool:
        """Return True if field_name matches a sensitive pattern.

        Sensitive fields include CTC/salary, equity/RSU, nationality/citizenship,
        and experience-years questions for unknown skills.
        """
        return bool(_SENSITIVE_REGEX.search(field_name))

    # ------------------------------------------------------------------
    # Field classification
    # ------------------------------------------------------------------

    def classify_fields(
        self,
        fields: list[dict[str, Any]],
        candidate_profile: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Classify form fields into auto-fillable and needs-human-input.

        Each field dict is expected to have at least a ``name`` or ``label`` key.

        Args:
            fields: List of field descriptors from the application form.
            candidate_profile: Candidate profile dict (keys like notice_period,
                willing_to_relocate, work_authorization, preferred_cities).

        Returns:
            Tuple of (auto_fillable, needs_human) where each element is a list
            of field dicts augmented with an ``autofill_value`` key (for
            auto_fillable fields) or left unchanged (for needs_human).
        """
        auto_fillable: list[dict[str, Any]] = []
        needs_human: list[dict[str, Any]] = []

        for field in fields:
            field_label = str(
                field.get("label", field.get("name", ""))
            ).lower()

            # 1. Sensitive fields always require human input
            if self.is_sensitive_field(field_label):
                needs_human.append(field)
                continue

            # 2. Try to match against the auto-fill map
            matched_key = self._match_autofill_key(field_label)
            if matched_key and matched_key in candidate_profile:
                enriched = {**field, "autofill_value": candidate_profile[matched_key]}
                auto_fillable.append(enriched)
                continue

            # 3. Default: needs human review
            needs_human.append(field)

        return auto_fillable, needs_human

    @staticmethod
    def _match_autofill_key(field_label: str) -> str | None:
        """Return the candidate_profile key that matches *field_label*, or None."""
        for key, pattern in _AUTOFILL_PATTERNS.items():
            if pattern.search(field_label):
                return key
        return None

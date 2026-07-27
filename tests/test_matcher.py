"""Unit tests for linkedin_agent.matcher module."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from linkedin_agent.matcher import JobMatcher


# ===========================================================================
# Match score computation
# ===========================================================================


class TestMatchScore:
    """Tests for compute_match_score and threshold logic."""

    def test_perfect_score(self):
        assert JobMatcher.compute_match_score(5, 5) == 1.0

    def test_partial_score(self):
        score = JobMatcher.compute_match_score(4, 5)
        assert score == pytest.approx(0.8)

    def test_zero_required_returns_zero(self):
        """Avoid division by zero."""
        assert JobMatcher.compute_match_score(3, 0) == 0.0

    def test_negative_required_returns_zero(self):
        assert JobMatcher.compute_match_score(3, -1) == 0.0

    def test_over_matched_caps_at_one(self):
        """If matched > required, cap at 1.0."""
        assert JobMatcher.compute_match_score(10, 5) == 1.0

    def test_zero_matched(self):
        assert JobMatcher.compute_match_score(0, 5) == 0.0

    def test_meets_threshold_exact(self):
        matcher = JobMatcher(threshold=0.80)
        assert matcher.meets_threshold(0.80) is True

    def test_meets_threshold_above(self):
        matcher = JobMatcher(threshold=0.80)
        assert matcher.meets_threshold(0.85) is True

    def test_below_threshold(self):
        matcher = JobMatcher(threshold=0.80)
        assert matcher.meets_threshold(0.79) is False

    def test_custom_threshold(self):
        matcher = JobMatcher(threshold=0.50)
        assert matcher.meets_threshold(0.50) is True
        assert matcher.meets_threshold(0.49) is False


# ===========================================================================
# Deduplication
# ===========================================================================


class TestDeduplication:
    """Tests for deduplication logic."""

    def test_not_duplicate_initially(self, mock_applied_file):
        matcher = JobMatcher(threshold=0.80)
        assert matcher.is_duplicate("TechCorp", "Backend Engineer") is False

    def test_is_duplicate_after_add(self, mock_applied_file):
        matcher = JobMatcher(threshold=0.80)
        matcher.add_to_applied("TechCorp", "Backend Engineer")
        assert matcher.is_duplicate("TechCorp", "Backend Engineer") is True

    def test_dedup_case_insensitive(self, mock_applied_file):
        matcher = JobMatcher(threshold=0.80)
        matcher.add_to_applied("TechCorp", "Backend Engineer")
        assert matcher.is_duplicate("techcorp", "backend engineer") is True
        assert matcher.is_duplicate("TECHCORP", "BACKEND ENGINEER") is True

    def test_dedup_trims_whitespace(self, mock_applied_file):
        matcher = JobMatcher(threshold=0.80)
        matcher.add_to_applied("  TechCorp  ", "  Backend Engineer  ")
        assert matcher.is_duplicate("TechCorp", "Backend Engineer") is True

    def test_different_title_not_duplicate(self, mock_applied_file):
        matcher = JobMatcher(threshold=0.80)
        matcher.add_to_applied("TechCorp", "Backend Engineer")
        assert matcher.is_duplicate("TechCorp", "Frontend Engineer") is False

    def test_different_company_not_duplicate(self, mock_applied_file):
        matcher = JobMatcher(threshold=0.80)
        matcher.add_to_applied("TechCorp", "Backend Engineer")
        assert matcher.is_duplicate("OtherCorp", "Backend Engineer") is False

    def test_persistence_to_disk(self, mock_applied_file):
        """Applied jobs should be persisted to disk."""
        matcher = JobMatcher(threshold=0.80)
        matcher.add_to_applied("TechCorp", "Backend Engineer")

        # Check the file was written
        assert mock_applied_file.exists()
        data = json.loads(mock_applied_file.read_text())
        assert isinstance(data, list)
        assert len(data) == 1

    def test_loads_from_disk(self, mock_applied_file):
        """A new JobMatcher should load existing applied jobs from disk."""
        # Pre-populate the file
        mock_applied_file.parent.mkdir(parents=True, exist_ok=True)
        mock_applied_file.write_text(json.dumps(["techcorp||backend engineer"]))

        matcher = JobMatcher(threshold=0.80)
        assert matcher.is_duplicate("TechCorp", "Backend Engineer") is True

    def test_corrupted_file_starts_fresh(self, mock_applied_file):
        """Corrupted JSON file should not crash — start with empty set."""
        mock_applied_file.parent.mkdir(parents=True, exist_ok=True)
        mock_applied_file.write_text("not valid json {{{")

        matcher = JobMatcher(threshold=0.80)
        assert matcher.is_duplicate("TechCorp", "Backend Engineer") is False


# ===========================================================================
# Sensitive field detection
# ===========================================================================


class TestSensitiveFields:
    """Tests for is_sensitive_field detection."""

    @pytest.mark.parametrize(
        "field_name",
        [
            "Current CTC",
            "Expected salary",
            "Total compensation",
            "What is your current package?",
            "Fixed component",
            "Variable pay",
            "RSU value",
            "Equity in current company",
            "Stock options",
            "ESOP details",
            "Vesting schedule",
            "Nationality",
            "Citizenship status",
            "Passport number",
            "Country of origin",
            "Years of experience in React",
            "How many years experience do you have",
        ],
    )
    def test_sensitive_fields_detected(self, field_name):
        assert JobMatcher.is_sensitive_field(field_name) is True

    @pytest.mark.parametrize(
        "field_name",
        [
            "Phone number",
            "Email address",
            "City",
            "Notice period",
            "Are you willing to relocate?",
            "Work authorization",
            "Full name",
        ],
    )
    def test_non_sensitive_fields_not_flagged(self, field_name):
        assert JobMatcher.is_sensitive_field(field_name) is False


# ===========================================================================
# Field classification
# ===========================================================================


class TestFieldClassification:
    """Tests for classify_fields method."""

    def test_notice_period_auto_filled(self, mock_applied_file, sample_candidate):
        matcher = JobMatcher(threshold=0.80)
        fields = [{"label": "What is your notice period?", "type": "text"}]
        profile = {"notice_period": sample_candidate.notice_period}

        auto, human = matcher.classify_fields(fields, profile)
        assert len(auto) == 1
        assert auto[0]["autofill_value"] == "30 days"
        assert len(human) == 0

    def test_relocation_auto_filled(self, mock_applied_file, sample_candidate):
        matcher = JobMatcher(threshold=0.80)
        fields = [{"label": "Are you willing to relocate?", "type": "radio"}]
        profile = {"willing_to_relocate": sample_candidate.willing_to_relocate}

        auto, human = matcher.classify_fields(fields, profile)
        assert len(auto) == 1
        assert auto[0]["autofill_value"] is True

    def test_sensitive_field_goes_to_human(self, mock_applied_file):
        matcher = JobMatcher(threshold=0.80)
        fields = [{"label": "What is your current CTC?", "type": "text"}]
        profile = {"notice_period": "30 days"}

        auto, human = matcher.classify_fields(fields, profile)
        assert len(auto) == 0
        assert len(human) == 1

    def test_unknown_field_goes_to_human(self, mock_applied_file):
        matcher = JobMatcher(threshold=0.80)
        fields = [{"label": "Tell us about your hobbies", "type": "textarea"}]
        profile = {"notice_period": "30 days"}

        auto, human = matcher.classify_fields(fields, profile)
        assert len(auto) == 0
        assert len(human) == 1

    def test_mixed_fields(self, mock_applied_file, sample_candidate):
        matcher = JobMatcher(threshold=0.80)
        fields = [
            {"label": "Notice period", "type": "text"},
            {"label": "Current CTC", "type": "text"},
            {"label": "Work authorization", "type": "select"},
            {"label": "Describe a project", "type": "textarea"},
        ]
        profile = {
            "notice_period": "30 days",
            "work_authorization": "Authorized to work",
        }

        auto, human = matcher.classify_fields(fields, profile)
        assert len(auto) == 2  # notice_period + work_authorization
        assert len(human) == 2  # CTC (sensitive) + describe (unknown)

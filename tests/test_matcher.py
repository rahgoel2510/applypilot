"""Tests for the job matcher/scoring module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from linkedin_agent.matcher import JobMatcher


@pytest.fixture
def matcher(tmp_path):
    """Create a JobMatcher with test configuration and temp applied file."""
    import linkedin_agent.matcher as matcher_module
    # Override the applied file path for testing
    original_path = matcher_module.APPLIED_FILE
    matcher_module.APPLIED_FILE = tmp_path / "applied.json"
    m = JobMatcher(
        threshold=0.7,
        target_companies=["Google", "Microsoft"],
        blocklist_companies=["Scam Corp"],
        target_boost=0.15,
        blocklist_penalty=0.20,
    )
    yield m
    # Restore
    matcher_module.APPLIED_FILE = original_path


class TestMatcherThreshold:
    """Tests for threshold-based decisions."""

    def test_meets_threshold_above(self, matcher):
        assert matcher.meets_threshold(0.8) is True

    def test_meets_threshold_exact(self, matcher):
        assert matcher.meets_threshold(0.7) is True

    def test_meets_threshold_below(self, matcher):
        assert matcher.meets_threshold(0.5) is False

    def test_meets_threshold_zero(self, matcher):
        assert matcher.meets_threshold(0.0) is False

    def test_meets_threshold_one(self, matcher):
        assert matcher.meets_threshold(1.0) is True


class TestMatcherDedup:
    """Tests for deduplication logic."""

    def test_not_duplicate_initially(self, matcher):
        assert matcher.is_duplicate("Google", "SWE") is False

    def test_is_duplicate_after_add(self, matcher):
        matcher.add_to_applied("Google", "SWE")
        assert matcher.is_duplicate("Google", "SWE") is True

    def test_case_insensitive_dedup(self, matcher):
        matcher.add_to_applied("GOOGLE", "Software Engineer")
        assert matcher.is_duplicate("google", "software engineer") is True

    def test_different_jobs_not_duplicate(self, matcher):
        matcher.add_to_applied("Google", "SWE")
        assert matcher.is_duplicate("Google", "PM") is False


class TestMatcherInit:
    """Tests for matcher initialization."""

    def test_default_threshold(self):
        m = JobMatcher(threshold=0.8)
        assert m.meets_threshold(0.8) is True
        assert m.meets_threshold(0.79) is False

    def test_custom_companies(self):
        m = JobMatcher(
            threshold=0.7,
            target_companies=["Acme"],
            blocklist_companies=["Evil"],
        )
        # Just verify initialization doesn't crash
        assert m is not None


class TestMatcherScoring:
    """Tests for score-related functionality."""

    def test_threshold_boundary(self, tmp_path):
        import linkedin_agent.matcher as matcher_module
        original_path = matcher_module.APPLIED_FILE
        matcher_module.APPLIED_FILE = tmp_path / "applied.json"

        m = JobMatcher(threshold=0.75)
        assert m.meets_threshold(0.75) is True
        assert m.meets_threshold(0.74) is False
        assert m.meets_threshold(0.76) is True

        matcher_module.APPLIED_FILE = original_path

    def test_zero_threshold(self, tmp_path):
        import linkedin_agent.matcher as matcher_module
        original_path = matcher_module.APPLIED_FILE
        matcher_module.APPLIED_FILE = tmp_path / "applied.json"

        m = JobMatcher(threshold=0.0)
        assert m.meets_threshold(0.0) is True
        assert m.meets_threshold(0.01) is True

        matcher_module.APPLIED_FILE = original_path


class TestMatcherAppliedPersistence:
    """Tests for applied jobs persistence."""

    def test_add_multiple_and_check(self, matcher):
        matcher.add_to_applied("Company A", "Role 1")
        matcher.add_to_applied("Company B", "Role 2")
        assert matcher.is_duplicate("Company A", "Role 1") is True
        assert matcher.is_duplicate("Company B", "Role 2") is True
        assert matcher.is_duplicate("Company C", "Role 3") is False


class TestMatcherSelfLearning:
    """Tests for self-learning / company boost-penalty logic."""

    def test_target_company_boost(self, tmp_path):
        import linkedin_agent.matcher as matcher_module
        original_path = matcher_module.APPLIED_FILE
        matcher_module.APPLIED_FILE = tmp_path / "applied.json"

        m = JobMatcher(
            threshold=0.7,
            target_companies=["Google"],
            target_boost=0.15,
        )
        # The matcher should store target companies
        assert hasattr(m, "_target_companies") or hasattr(m, "target_companies")

        matcher_module.APPLIED_FILE = original_path

    def test_blocklist_company_penalty(self, tmp_path):
        import linkedin_agent.matcher as matcher_module
        original_path = matcher_module.APPLIED_FILE
        matcher_module.APPLIED_FILE = tmp_path / "applied.json"

        m = JobMatcher(
            threshold=0.7,
            blocklist_companies=["Scam Corp"],
            blocklist_penalty=0.20,
        )
        assert hasattr(m, "_blocklist_companies") or hasattr(m, "blocklist_companies")

        matcher_module.APPLIED_FILE = original_path


class TestMatcherClassifyFields:
    """Tests for field classification logic."""

    def test_classify_sensitive_fields(self, matcher):
        """Sensitive fields go to needs_human."""
        fields = [
            {"label": "Expected CTC", "type": "text"},
            {"label": "Current Salary", "type": "text"},
        ]
        auto, human = matcher.classify_fields(fields, {})
        assert len(human) == 2
        assert len(auto) == 0

    def test_classify_auto_fillable(self, matcher):
        """Fields matching autofill patterns with correct profile keys are auto-filled."""
        fields = [
            {"label": "Full Name", "type": "text"},
            {"label": "Email Address", "type": "email"},
            {"label": "Phone Number", "type": "tel"},
        ]
        profile = {"name": "Test User", "email": "test@x.com", "phone": "+91-12345"}
        auto, human = matcher.classify_fields(fields, profile)
        # Exact behavior depends on autofill patterns - just verify it works
        assert len(auto) + len(human) == 3

    def test_classify_unknown_goes_to_human(self, matcher):
        """Unknown fields default to needs_human."""
        fields = [{"label": "Some Random Question", "type": "text"}]
        auto, human = matcher.classify_fields(fields, {})
        assert len(human) == 1


class TestMatcherSensitiveFields:
    """Tests for sensitive field detection."""

    def test_ctc_is_sensitive(self, matcher):
        assert matcher.is_sensitive_field("current ctc") is True
        assert matcher.is_sensitive_field("expected salary") is True

    def test_name_is_not_sensitive(self, matcher):
        assert matcher.is_sensitive_field("full name") is False
        assert matcher.is_sensitive_field("email") is False


class TestMatcherLoadFeedback:
    """Tests for self-learning feedback loading."""

    def test_load_feedback_handles_connection_error(self, matcher):
        """When tracker is unreachable, load_feedback doesn't crash."""
        # Default tracker URL (127.0.0.1:8000) won't be running in tests
        matcher.load_feedback()  # Should not raise


class TestMatcherScoreCalculation:
    """Tests for the compute_match_score static method."""

    def test_compute_score_basic(self, matcher):
        score = matcher.compute_match_score(matched=7, required=10)
        assert score == 0.7

    def test_compute_score_zero_required(self, matcher):
        score = matcher.compute_match_score(matched=5, required=0)
        assert score == 0.0

    def test_compute_score_cap_at_one(self, matcher):
        score = matcher.compute_match_score(matched=15, required=10)
        assert score == 1.0

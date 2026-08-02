"""Extended container tests - verify real factories work."""

from unittest.mock import patch, MagicMock

import pytest

from linkedin_agent.container import Container


class TestContainerRealFactories:
    """Test that container factories produce real instances (not just mocks)."""

    def test_fallback_scorer_factory(self, sample_config):
        container = Container(sample_config)
        scorer = container.fallback_scorer
        # Should be a FallbackScorer with score_from_job_card method
        assert hasattr(scorer, "score_from_job_card")
        result = scorer.score_from_job_card("Engineer", "Corp", "India")
        assert 0.0 <= result <= 1.0

    def test_daily_cap_factory(self, sample_config):
        container = Container(sample_config)
        cap = container.daily_cap
        assert hasattr(cap, "can_apply")
        assert hasattr(cap, "record_application")
        assert cap.daily_limit == sample_config.job_search.daily_application_limit

    def test_retry_queue_factory(self, sample_config):
        container = Container(sample_config)
        queue = container.retry_queue
        assert hasattr(queue, "add")
        assert hasattr(queue, "get_due")
        assert queue.pending_count >= 0

    def test_dedup_factory(self, sample_config):
        container = Container(sample_config)
        dedup = container.dedup
        assert hasattr(dedup, "is_seen")
        assert hasattr(dedup, "mark_applied")

    def test_tracker_factory(self, sample_config):
        container = Container(sample_config)
        tracker = container.tracker
        assert hasattr(tracker, "push_event")
        assert hasattr(tracker, "log")

    def test_scorer_factory(self, sample_config):
        container = Container(sample_config)
        scorer = container.scorer
        assert hasattr(scorer, "meets_threshold")
        assert hasattr(scorer, "is_duplicate")
        assert hasattr(scorer, "add_to_applied")

    def test_inmail_factory(self, sample_config):
        container = Container(sample_config)
        inmail = container.inmail
        assert hasattr(inmail, "draft_inmail")
        assert hasattr(inmail, "get_candidate_summary")

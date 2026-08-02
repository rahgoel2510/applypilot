"""Tests for the fallback keyword-based scorer."""

import pytest

from linkedin_agent.fallback_scorer import FallbackScorer


@pytest.fixture
def scorer():
    """Create a FallbackScorer with test configuration."""
    return FallbackScorer(
        search_keywords=["Engineering Manager", "Technical Program Manager"],
        skills=["system design", "agile", "leadership", "python"],
        preferred_cities=["Bangalore", "Hyderabad"],
        locations=["India", "Remote"],
    )


class TestFallbackScorerBasics:
    """Tests for basic scoring."""

    def test_perfect_match(self, scorer):
        """Title and location match should score high."""
        score = scorer.score_from_job_card(
            title="Engineering Manager",
            company="TechCorp",
            location="Bangalore, India",
        )
        assert score > 0.6

    def test_no_match(self, scorer):
        """Completely irrelevant job should score low."""
        score = scorer.score_from_job_card(
            title="Truck Driver",
            company="Logistics Inc",
            location="Alaska, USA",
        )
        assert score < 0.3

    def test_partial_match(self, scorer):
        """Some keyword overlap should produce moderate score."""
        score = scorer.score_from_job_card(
            title="Senior Technical Lead",
            company="Agile Solutions",
            location="Remote",
        )
        assert 0.2 < score < 0.9

    def test_score_range(self, scorer):
        """Score should always be 0.0-1.0."""
        score = scorer.score_from_job_card(
            title="Random Job",
            company="Random Corp",
            location="Nowhere",
        )
        assert 0.0 <= score <= 1.0


class TestFallbackScorerLocation:
    """Tests for location matching."""

    def test_preferred_city_boost(self, scorer):
        """Preferred city should score higher than non-preferred."""
        score_preferred = scorer.score_from_job_card(
            title="Manager",
            company="Corp",
            location="Bangalore, India",
        )
        score_other = scorer.score_from_job_card(
            title="Manager",
            company="Corp",
            location="Tokyo, Japan",
        )
        assert score_preferred > score_other

    def test_remote_matches(self, scorer):
        """Remote location should match 'Remote' in locations config."""
        score = scorer.score_from_job_card(
            title="Engineering Manager",
            company="Corp",
            location="Remote",
        )
        assert score > 0.4


class TestFallbackScorerEdgeCases:
    """Edge cases for fallback scorer."""

    def test_empty_title(self, scorer):
        score = scorer.score_from_job_card(title="", company="Corp", location="India")
        assert 0.0 <= score <= 1.0

    def test_empty_location(self, scorer):
        score = scorer.score_from_job_card(
            title="Engineering Manager",
            company="Corp",
            location="",
        )
        assert 0.0 <= score <= 1.0

    def test_empty_everything(self, scorer):
        score = scorer.score_from_job_card(title="", company="", location="")
        assert score == 0.0 or score >= 0.0  # Should not crash

    def test_special_characters(self, scorer):
        score = scorer.score_from_job_card(
            title="Sr. Engineering Manager (Contract)",
            company="Tech & Co.",
            location="Bangalore / Remote",
        )
        assert 0.0 <= score <= 1.0

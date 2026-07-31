"""Unit tests for linkedin_agent.fallback_scorer module."""

from __future__ import annotations

import pytest

from linkedin_agent.fallback_scorer import FallbackScorer, get_fallback_scorer


# ===========================================================================
# FallbackScorer — score_from_job_card
# ===========================================================================


class TestScoreFromJobCard:
    """Tests for card-level scoring (title + company + location only)."""

    @pytest.fixture
    def scorer(self) -> FallbackScorer:
        return FallbackScorer(
            search_keywords=["Engineering Manager", "Technical Program Manager"],
            skills=[
                "engineering management",
                "system design",
                "agile",
                "microservices",
                "cloud infrastructure",
            ],
            preferred_cities=["Bangalore", "Hyderabad"],
            locations=["India", "Remote"],
        )

    def test_exact_title_match_high_score(self, scorer: FallbackScorer):
        """Exact title match should produce a high score."""
        score = scorer.score_from_job_card("Engineering Manager", "Google", "Bangalore")
        assert score >= 0.5, f"Expected >= 0.5 for exact title match, got {score}"

    def test_no_overlap_zero_score(self, scorer: FallbackScorer):
        """Completely unrelated job should score near zero."""
        score = scorer.score_from_job_card("Marketing Analyst", "HubSpot", "San Francisco")
        assert score <= 0.1, f"Expected <= 0.1 for no overlap, got {score}"

    def test_partial_title_overlap(self, scorer: FallbackScorer):
        """Partial keyword overlap should give a moderate score."""
        score = scorer.score_from_job_card(
            "Senior Software Engineer", "Microsoft", "Bangalore"
        )
        assert 0.1 <= score <= 0.6, f"Expected moderate score, got {score}"

    def test_location_match_boosts_score(self, scorer: FallbackScorer):
        """Same job in preferred city should score higher than unknown city."""
        score_blr = scorer.score_from_job_card("Engineering Manager", "Acme", "Bangalore")
        score_sf = scorer.score_from_job_card("Engineering Manager", "Acme", "San Francisco")
        assert score_blr > score_sf, "Preferred city should boost score"

    def test_remote_location_accepted(self, scorer: FallbackScorer):
        """Remote location should be treated favorably."""
        score = scorer.score_from_job_card("Engineering Manager", "Startup", "Remote")
        assert score >= 0.5, f"Remote + good title should score well, got {score}"

    def test_score_in_valid_range(self, scorer: FallbackScorer):
        """Score should always be between 0.0 and 1.0."""
        test_cases = [
            ("CTO", "BigCo", "Mars"),
            ("", "", ""),
            ("Engineering Manager", "Google", "Bangalore, Karnataka, India"),
        ]
        for title, company, loc in test_cases:
            score = scorer.score_from_job_card(title, company, loc)
            assert 0.0 <= score <= 1.0, f"Score out of range for ({title}, {company}, {loc})"


# ===========================================================================
# FallbackScorer — score_from_text
# ===========================================================================


class TestScoreFromText:
    """Tests for full JD scoring (title + company + description)."""

    @pytest.fixture
    def scorer(self) -> FallbackScorer:
        return FallbackScorer(
            search_keywords=["Engineering Manager", "Technical Program Manager"],
            skills=[
                "engineering management",
                "system design",
                "agile",
                "microservices",
                "cloud infrastructure",
                "team building",
            ],
            preferred_cities=["Bangalore"],
            locations=["India"],
        )

    def test_rich_jd_high_score(self, scorer: FallbackScorer):
        """JD with many matching keywords should score high."""
        jd = (
            "We are looking for an Engineering Manager to lead our cloud infrastructure "
            "team in Bangalore. You will drive system design, agile practices, and "
            "microservices architecture. Experience with team building required."
        )
        score = scorer.score_from_text("Engineering Manager", "Amazon", jd)
        assert score >= 0.6, f"Rich JD match should score >= 0.6, got {score}"

    def test_empty_jd_falls_back_to_title(self, scorer: FallbackScorer):
        """With no JD, scoring should still work from title alone."""
        score = scorer.score_from_text("Engineering Manager", "Google", "")
        assert score > 0.0, "Should still produce a score from title alone"

    def test_unrelated_jd_low_score(self, scorer: FallbackScorer):
        """Unrelated JD should produce a low score."""
        jd = "Marketing team seeking a social media manager to run campaigns."
        score = scorer.score_from_text("Social Media Manager", "Startup", jd)
        assert score <= 0.3, f"Unrelated JD should score low, got {score}"

    def test_jd_with_location_mention(self, scorer: FallbackScorer):
        """Location mentioned in JD should contribute to score."""
        jd = "Role is based in Bangalore. We need an agile practitioner."
        score_blr = scorer.score_from_text("Program Manager", "Co", jd)
        jd_no_loc = "Role is based in Tokyo. We need an agile practitioner."
        score_tok = scorer.score_from_text("Program Manager", "Co", jd_no_loc)
        assert score_blr >= score_tok, "Matching location in JD should help"


# ===========================================================================
# get_fallback_scorer factory
# ===========================================================================


class TestGetFallbackScorer:
    """Tests for the factory function."""

    def test_creates_scorer_from_config(self):
        """Should create a working scorer from a Settings-like object."""
        from unittest.mock import MagicMock

        config = MagicMock()
        config.job_search.keywords = ["Software Engineer", "Backend Developer"]
        config.job_search.locations = ["Remote"]
        config.candidate.skills = ["python", "aws", "docker"]
        config.candidate.preferred_cities = ["New York"]

        scorer = get_fallback_scorer(config)
        assert isinstance(scorer, FallbackScorer)

        # Should produce a valid score
        score = scorer.score_from_job_card("Software Engineer", "Meta", "Remote")
        assert 0.0 <= score <= 1.0

    def test_handles_empty_skills(self):
        """Should work even if skills list is empty."""
        from unittest.mock import MagicMock

        config = MagicMock()
        config.job_search.keywords = ["Data Scientist"]
        config.job_search.locations = []
        config.candidate.skills = []
        config.candidate.preferred_cities = []

        scorer = get_fallback_scorer(config)
        score = scorer.score_from_job_card("Data Scientist", "OpenAI", "SF")
        assert score > 0.0, "Should still match on keywords even without skills"

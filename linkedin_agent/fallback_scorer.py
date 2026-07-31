"""Fallback scoring module for when LinkedIn Premium match score is unavailable.

Uses simple TF-IDF-like keyword overlap logic to score jobs against the
candidate's configured keywords, skills, and location preferences. No external
ML dependencies required.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from linkedin_agent.config import Settings


class FallbackScorer:
    """Keyword-based job relevance scorer.

    Computes a 0.0–1.0 score based on:
    - Keyword overlap between job text and candidate keywords/skills
    - Exact title match bonus
    - Location match bonus
    - TF-IDF-like weighting (rarer keywords score higher)
    """

    # Weights for the scoring components
    KEYWORD_WEIGHT = 0.50
    TITLE_MATCH_WEIGHT = 0.30
    LOCATION_WEIGHT = 0.20

    def __init__(
        self,
        search_keywords: list[str],
        skills: list[str],
        preferred_cities: list[str],
        locations: list[str] | None = None,
    ) -> None:
        """Initialize with candidate profile keywords.

        Args:
            search_keywords: Job search keywords (e.g., ["Engineering Manager"]).
            skills: Candidate skills list from config.
            preferred_cities: Preferred city names from candidate config.
            locations: Search location filters from job_search config.
        """
        self.search_keywords = [k.lower().strip() for k in search_keywords if k.strip()]
        self.skills = [s.lower().strip() for s in skills if s.strip()]
        self.preferred_cities = [c.lower().strip() for c in preferred_cities if c.strip()]
        self.locations = [loc.lower().strip() for loc in (locations or []) if loc.strip()]

        # Build the full keyword corpus for TF-IDF weighting
        # Combine search keywords + skills into tokenized terms
        self._all_keywords = self.search_keywords + self.skills
        self._keyword_tokens = self._build_token_set(self._all_keywords)

        # IDF-like weighting: rarer tokens in our keyword set get higher weight
        token_counts = Counter(self._keyword_tokens)
        total_keywords = len(self._all_keywords) or 1
        self._token_idf: dict[str, float] = {}
        for token, count in token_counts.items():
            # Inverse frequency: tokens that appear in fewer keywords are more distinctive
            self._token_idf[token] = math.log(total_keywords / count) + 1.0

        # All location terms for matching
        self._location_terms = set(self.preferred_cities + self.locations)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text into lowercase alphanumeric words."""
        return re.findall(r"[a-z0-9]+", text.lower())

    def _build_token_set(self, phrases: list[str]) -> list[str]:
        """Tokenize a list of phrases into a flat list of tokens."""
        tokens = []
        for phrase in phrases:
            tokens.extend(self._tokenize(phrase))
        return tokens

    def _keyword_overlap_score(self, text: str) -> float:
        """Compute weighted keyword overlap between text and candidate keywords.

        Uses TF-IDF-like scoring: each token from our keywords found in the text
        contributes its IDF weight. Normalized to 0.0–1.0.
        """
        if not self._keyword_tokens or not text.strip():
            return 0.0

        text_tokens = set(self._tokenize(text))
        if not text_tokens:
            return 0.0

        # Score = sum of IDF weights for matched tokens / sum of all IDF weights
        total_weight = sum(self._token_idf.values())
        if total_weight == 0:
            return 0.0

        matched_weight = 0.0
        matched_tokens = set()
        for token, idf in self._token_idf.items():
            if token in text_tokens and token not in matched_tokens:
                matched_weight += idf
                matched_tokens.add(token)

        return min(matched_weight / total_weight, 1.0)

    def _exact_title_match_score(self, job_title: str) -> float:
        """Check if any search keyword appears as an exact (substring) match in the title.

        Returns 1.0 for exact match, 0.5 for partial overlap, 0.0 for no match.
        """
        title_lower = job_title.lower().strip()
        if not title_lower:
            return 0.0

        # Exact match: search keyword IS the title (or very close)
        for keyword in self.search_keywords:
            if keyword == title_lower:
                return 1.0
            if keyword in title_lower or title_lower in keyword:
                return 0.8

        # Partial: check word overlap between title and search keywords
        title_tokens = set(self._tokenize(title_lower))
        best_overlap = 0.0
        for keyword in self.search_keywords:
            kw_tokens = set(self._tokenize(keyword))
            if not kw_tokens:
                continue
            overlap = len(title_tokens & kw_tokens) / len(kw_tokens)
            best_overlap = max(best_overlap, overlap)

        return best_overlap * 0.6  # Scale partial matches down

    def _location_match_score(self, location: str) -> float:
        """Check if job location matches candidate's preferred cities/locations.

        Returns 1.0 for match, 0.0 for no match.
        """
        if not location or not self._location_terms:
            return 0.5  # Neutral when no location info available

        location_lower = location.lower().strip()
        location_tokens = set(self._tokenize(location_lower))

        # Check if any preferred location term appears in the job location
        for loc_term in self._location_terms:
            if loc_term in location_lower:
                return 1.0
            # Token-level check for partial matches (e.g., "delhi" in "Delhi NCR")
            loc_tokens = set(self._tokenize(loc_term))
            if loc_tokens and loc_tokens & location_tokens:
                return 0.8

        # "Remote" is always a good match
        if "remote" in location_lower:
            return 0.9

        return 0.0

    def score_from_text(
        self, job_title: str, company: str, job_description: str = ""
    ) -> float:
        """Score a job using its title, company, and full description.

        Args:
            job_title: The job title string.
            company: The company name.
            job_description: Full job description text (optional but improves accuracy).

        Returns:
            A relevance score between 0.0 and 1.0.
        """
        # Combine title + description for keyword matching
        full_text = f"{job_title} {company} {job_description}".strip()

        # Component scores
        keyword_score = self._keyword_overlap_score(full_text)
        title_score = self._exact_title_match_score(job_title)

        # Extract location from description if present (look for common patterns)
        location_hint = self._extract_location_from_text(job_description)
        location_score = self._location_match_score(location_hint)

        # Weighted combination
        final_score = (
            self.KEYWORD_WEIGHT * keyword_score
            + self.TITLE_MATCH_WEIGHT * title_score
            + self.LOCATION_WEIGHT * location_score
        )

        return min(max(final_score, 0.0), 1.0)

    def score_from_job_card(
        self, title: str, company: str, location: str
    ) -> float:
        """Score a job from card-level info only (no full JD available).

        Uses title and location since that's all we have from the listing card.

        Args:
            title: Job title from the card.
            company: Company name from the card.
            location: Location string from the card.

        Returns:
            A relevance score between 0.0 and 1.0.
        """
        # With no JD, we rely more heavily on title match and location
        keyword_score = self._keyword_overlap_score(f"{title} {company}")
        title_score = self._exact_title_match_score(title)
        location_score = self._location_match_score(location)

        # Reweight: title matters more when we have no description
        final_score = (
            0.35 * keyword_score
            + 0.40 * title_score
            + 0.25 * location_score
        )

        return min(max(final_score, 0.0), 1.0)

    def _extract_location_from_text(self, text: str) -> str:
        """Try to extract location info from job description text.

        Looks for common patterns like 'Location: X' or city names.
        """
        if not text:
            return ""

        # Check for explicit location patterns
        patterns = [
            r"location[:\s]+([^\n,]+)",
            r"based in\s+([^\n,\.]+)",
            r"office in\s+([^\n,\.]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(1).strip()

        # Check if any of our known location terms appear in the text
        text_lower = text.lower()
        for loc in self._location_terms:
            if loc in text_lower:
                return loc

        return ""


def get_fallback_scorer(config: Settings) -> FallbackScorer:
    """Factory function to create a FallbackScorer from application config.

    Args:
        config: The application Settings instance.

    Returns:
        A configured FallbackScorer instance.
    """
    search_keywords = list(config.job_search.keywords)
    skills = list(getattr(config.candidate, "skills", []))
    preferred_cities = list(config.candidate.preferred_cities)
    locations = list(config.job_search.locations)

    return FallbackScorer(
        search_keywords=search_keywords,
        skills=skills,
        preferred_cities=preferred_cities,
        locations=locations,
    )

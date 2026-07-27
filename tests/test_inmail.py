"""Unit tests for linkedin_agent.inmail module."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linkedin_agent.inmail import (
    InMailDrafter,
    FALLBACK_INMAIL_TEMPLATE,
    FALLBACK_CONNECTION_TEMPLATE,
)


# ===========================================================================
# Fallback templates
# ===========================================================================


class TestFallbackTemplates:
    """Tests for fallback template rendering."""

    def test_inmail_template_renders(self, sample_settings):
        """Fallback InMail template renders with all placeholders."""
        drafter = InMailDrafter(sample_settings)
        result = drafter._fallback_inmail(
            job_title="Backend Engineer",
            company="TechCorp",
            recruiter_name="Priya Sharma",
            candidate_summary="5 years Python, distributed systems",
        )

        assert "Priya" in result
        assert "Backend Engineer" in result
        assert "TechCorp" in result
        assert "Rahul" in result  # candidate first name

    def test_inmail_template_no_candidate_name(self, sample_settings):
        """Handles missing candidate name gracefully."""
        from linkedin_agent.config import Settings, CandidateConfig

        settings_no_name = Settings(
            candidate=CandidateConfig(name=""),
            openai_api_key="fake",
        )
        drafter = InMailDrafter(settings_no_name)
        result = drafter._fallback_inmail(
            job_title="Engineer",
            company="Corp",
            recruiter_name="John Doe",
            candidate_summary="Experienced developer",
        )
        assert "Best regards" in result

    def test_connection_template_renders(self):
        """Fallback connection template renders properly."""
        result = FALLBACK_CONNECTION_TEMPLATE.format(
            recruiter_name="Priya",
            job_title="Backend Engineer",
            company="TechCorp",
        )
        assert "Priya" in result
        assert "Backend Engineer" in result
        assert len(result) <= 300


# ===========================================================================
# Cache logic
# ===========================================================================


class TestDraftCache:
    """Tests for draft caching and persistence."""

    def test_cache_key_deterministic(self, sample_settings):
        """Same inputs produce same cache key."""
        drafter = InMailDrafter(sample_settings)
        key1 = drafter._cache_key("Engineer", "Corp", "John")
        key2 = drafter._cache_key("Engineer", "Corp", "John")
        assert key1 == key2

    def test_cache_key_case_insensitive(self, sample_settings):
        """Cache key is case-normalized."""
        drafter = InMailDrafter(sample_settings)
        key1 = drafter._cache_key("Engineer", "Corp", "John")
        key2 = drafter._cache_key("engineer", "corp", "john")
        assert key1 == key2

    def test_cache_key_different_for_different_inputs(self, sample_settings):
        """Different inputs produce different cache keys."""
        drafter = InMailDrafter(sample_settings)
        key1 = drafter._cache_key("Engineer", "Corp", "John")
        key2 = drafter._cache_key("Designer", "Corp", "John")
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_cached_draft_returned(self, sample_settings, mock_drafts_file):
        """If a draft is cached, it's returned without calling OpenAI."""
        drafter = InMailDrafter(sample_settings)

        # Manually populate cache
        cache_key = drafter._cache_key("Engineer", "Corp", "Recruiter")
        drafter._cache[cache_key] = {"draft": "Cached message"}

        with patch.object(drafter, "_generate", new_callable=AsyncMock) as mock_gen:
            result = await drafter.draft_inmail(
                job_title="Engineer",
                company="Corp",
                recruiter_name="Recruiter",
                job_description="Some JD",
                candidate_summary="Summary",
            )

        assert result == "Cached message"
        mock_gen.assert_not_called()

    def test_load_cache_from_disk(self, sample_settings, mock_drafts_file):
        """Cache is loaded from disk file if it exists."""
        mock_drafts_file.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {"abc123": {"draft": "Saved draft", "type": "inmail"}}
        mock_drafts_file.write_text(json.dumps(cache_data))

        drafter = InMailDrafter(sample_settings)
        assert "abc123" in drafter._cache
        assert drafter._cache["abc123"]["draft"] == "Saved draft"

    def test_corrupted_cache_starts_empty(self, sample_settings, mock_drafts_file):
        """Corrupted cache file doesn't crash — starts fresh."""
        mock_drafts_file.parent.mkdir(parents=True, exist_ok=True)
        mock_drafts_file.write_text("not json!!!")

        drafter = InMailDrafter(sample_settings)
        assert drafter._cache == {}

    @pytest.mark.asyncio
    async def test_draft_saved_to_cache(self, sample_settings, mock_drafts_file):
        """After generating, draft is saved to cache and persisted."""
        drafter = InMailDrafter(sample_settings)

        with patch.object(
            drafter, "_generate", new_callable=AsyncMock, return_value="Generated draft"
        ):
            result = await drafter.draft_inmail(
                job_title="Engineer",
                company="TechCorp",
                recruiter_name="Jane",
                job_description="Build APIs",
                candidate_summary="5 years Python",
            )

        assert result == "Generated draft"
        # Check it's in cache
        cache_key = drafter._cache_key("Engineer", "TechCorp", "Jane")
        assert cache_key in drafter._cache
        assert drafter._cache[cache_key]["draft"] == "Generated draft"


# ===========================================================================
# OpenAI fallback
# ===========================================================================


class TestOpenAIFallback:
    """Tests for API error fallback behaviour."""

    @pytest.mark.asyncio
    async def test_api_error_uses_fallback(self, sample_settings, mock_drafts_file):
        """When OpenAI raises, fallback template is used."""
        from openai import APIConnectionError

        drafter = InMailDrafter(sample_settings)

        with patch.object(
            drafter._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=APIConnectionError(request=MagicMock()),
        ):
            result = await drafter.draft_inmail(
                job_title="Engineer",
                company="TechCorp",
                recruiter_name="Priya Sharma",
                job_description="Build scalable APIs",
                candidate_summary="5 years Python",
            )

        # Should contain fallback content
        assert "Priya" in result
        assert "Engineer" in result
        assert "TechCorp" in result

    @pytest.mark.asyncio
    async def test_empty_response_uses_fallback(self, sample_settings, mock_drafts_file):
        """Empty OpenAI response triggers fallback."""
        drafter = InMailDrafter(sample_settings)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""

        with patch.object(
            drafter._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await drafter.draft_inmail(
                job_title="Engineer",
                company="Corp",
                recruiter_name="John",
                job_description="JD",
                candidate_summary="Summary",
            )

        # Fallback template will be used
        assert "Engineer" in result


# ===========================================================================
# Connection note
# ===========================================================================


class TestConnectionNote:
    """Tests for connection note generation."""

    @pytest.mark.asyncio
    async def test_connection_note_length_limit(self, sample_settings, mock_drafts_file):
        """Connection note is capped at 300 characters."""
        drafter = InMailDrafter(sample_settings)

        # Return a very long string from _generate
        long_text = "A" * 500
        with patch.object(
            drafter, "_generate", new_callable=AsyncMock, return_value=long_text
        ):
            result = await drafter.draft_connection_note(
                recruiter_name="Priya",
                job_title="Engineer",
                company="Corp",
            )

        assert len(result) <= 300
        assert result.endswith("...")


# ===========================================================================
# Candidate summary
# ===========================================================================


class TestCandidateSummary:
    """Tests for get_candidate_summary helper."""

    def test_full_summary(self, sample_settings):
        drafter = InMailDrafter(sample_settings)
        summary = drafter.get_candidate_summary()

        assert "Rahul Goel" in summary
        assert "30 days" in summary
        assert "Bangalore" in summary
        assert "relocation" in summary.lower() or "Open to relocation" in summary

    def test_empty_candidate_summary(self):
        """Candidate config with all blank fields gives default summary."""
        from linkedin_agent.config import Settings, CandidateConfig

        settings = Settings(
            candidate=CandidateConfig(
                name="",
                email="",
                phone="",
                notice_period="",
                willing_to_relocate=False,
                work_authorization="",
                preferred_cities=[],
            ),
            openai_api_key="fake",
        )
        drafter = InMailDrafter(settings)
        summary = drafter.get_candidate_summary()
        assert "Experienced professional" in summary

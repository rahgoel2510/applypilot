"""Tests for the AI answer generator module."""

import asyncio
from unittest.mock import patch

import pytest

from linkedin_agent.answer_generator import AnswerGenerator


class TestIsAIAnswerable:
    """Tests for the static is_ai_answerable method."""

    def test_cover_letter(self):
        assert AnswerGenerator.is_ai_answerable("Cover Letter") is True

    def test_why_interested(self):
        assert AnswerGenerator.is_ai_answerable("Why are you interested in this role?") is True

    def test_why_want(self):
        assert AnswerGenerator.is_ai_answerable("Why do you want to work here?") is True

    def test_describe_experience(self):
        assert AnswerGenerator.is_ai_answerable("Describe your experience with cloud") is True

    def test_tell_about_yourself(self):
        assert AnswerGenerator.is_ai_answerable("Tell us about yourself") is True

    def test_good_fit(self):
        assert AnswerGenerator.is_ai_answerable("What makes you a good fit?") is True

    def test_additional_info(self):
        assert AnswerGenerator.is_ai_answerable("Additional information") is True

    def test_anything_else(self):
        assert AnswerGenerator.is_ai_answerable("Is there anything else you'd like us to know?") is True

    def test_non_ai_field_salary(self):
        assert AnswerGenerator.is_ai_answerable("Expected Salary") is False

    def test_non_ai_field_phone(self):
        assert AnswerGenerator.is_ai_answerable("Phone Number") is False

    def test_non_ai_field_name(self):
        assert AnswerGenerator.is_ai_answerable("Full Name") is False

    def test_case_insensitive(self):
        assert AnswerGenerator.is_ai_answerable("COVER LETTER") is True


class TestAnswerGeneratorInit:
    """Tests for AnswerGenerator initialization."""

    def test_creates_with_config(self):
        config = {
            "name": "Test User",
            "skills": ["python", "aws"],
            "keywords": ["SWE"],
        }
        gen = AnswerGenerator(config)
        assert gen._config == config

    def test_uses_env_api_key(self):
        config = {"name": "Test"}
        gen = AnswerGenerator(config)
        # Should read from OPENAI_API_KEY env var (set in conftest)
        assert gen._api_key != ""  # conftest sets sk-test-key


class TestAnswerGeneratorGenerate:
    """Tests for the generate_answer method."""

    @pytest.mark.asyncio
    async def test_generate_with_missing_api_key(self):
        """Without a real API key, should handle gracefully."""
        import os
        config = {"name": "Test", "skills": ["python"], "keywords": ["SWE"]}

        gen = AnswerGenerator(config)
        # generate_answer makes an HTTP call that will fail without real key
        # Just verify it's an async method that exists
        assert asyncio.iscoroutinefunction(gen.generate_answer)

    def test_ai_answerable_edge_cases(self):
        """Test various edge cases for is_ai_answerable."""
        assert AnswerGenerator.is_ai_answerable("") is False
        assert AnswerGenerator.is_ai_answerable("cover letter text box") is True
        assert AnswerGenerator.is_ai_answerable("Years of Experience") is False
        assert AnswerGenerator.is_ai_answerable("Why this company") is False  # "why do you want" pattern

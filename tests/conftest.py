"""Shared fixtures for LinkedIn Job Agent tests."""

from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linkedin_agent.config import (
    CandidateConfig,
    InmailConfig,
    JobSearchConfig,
    SchedulerConfig,
    Settings,
    TelegramConfig,
    reset_config,
)


# ---------------------------------------------------------------------------
# Fixtures: Config
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Ensure each test starts with a fresh config singleton."""
    reset_config()
    yield
    reset_config()


@pytest.fixture
def sample_candidate() -> CandidateConfig:
    """Provide a realistic candidate config for testing."""
    return CandidateConfig(
        name="Rahul Goel",
        email="rahul@example.com",
        phone="+919876543210",
        resume_filename="RAHUL_GOEL_Resume_Final.pdf",
        notice_period="30 days",
        willing_to_relocate=True,
        work_authorization="Authorized to work",
        preferred_cities=["Bangalore", "Hyderabad", "Mumbai"],
    )


@pytest.fixture
def sample_settings(sample_candidate) -> Settings:
    """Provide a full Settings object for testing (no real secrets)."""
    return Settings(
        candidate=sample_candidate,
        job_search=JobSearchConfig(
            match_threshold=0.80,
            max_postings_per_run=50,
            collection="Recommended",
            skip_external_apply=True,
        ),
        scheduler=SchedulerConfig(
            interval_minutes=60,
            active_hours_start=9,
            active_hours_end=22,
        ),
        telegram=TelegramConfig(
            bot_token="fake-bot-token",
            chat_id="fake-chat-id",
            notify_on_submit=True,
            notify_on_pause=True,
            notify_on_skip=False,
            tally_interval_minutes=30,
        ),
        inmail=InmailConfig(
            enabled=True,
            tone="professional",
            max_length=300,
        ),
        openai_api_key="fake-openai-key",
        linkedin_email="fake@example.com",
        linkedin_password="fake-password",
    )


# ---------------------------------------------------------------------------
# Fixtures: Temp directories (for dedup files, cache, etc.)
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide a temporary directory and patch relevant module paths."""
    return tmp_path


@pytest.fixture
def mock_applied_file(tmp_path):
    """Patch the APPLIED_FILE path to use a temp file."""
    applied_path = tmp_path / "applied.json"
    with patch("linkedin_agent.matcher.APPLIED_FILE", applied_path):
        yield applied_path


@pytest.fixture
def mock_drafts_file(tmp_path):
    """Patch the DRAFTS_FILE path to use a temp file."""
    drafts_dir = tmp_path / ".linkedin_agent"
    drafts_file = drafts_dir / "inmail_drafts.json"
    with patch("linkedin_agent.inmail.DRAFTS_DIR", drafts_dir), \
         patch("linkedin_agent.inmail.DRAFTS_FILE", drafts_file):
        yield drafts_file


# ---------------------------------------------------------------------------
# Fixtures: Sample job data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_job() -> dict:
    """A typical job posting dict as returned by the browser module."""
    return {
        "id": "job-12345",
        "title": "Senior Backend Engineer",
        "company": "TechCorp",
        "location": "Bangalore, India",
        "is_external": False,
        "match_score": 0.85,
        "matched_qualifications": 6,
        "required_qualifications": 7,
        "description": "We're looking for a Senior Backend Engineer...",
        "recruiter": "Priya Sharma",
    }


@pytest.fixture
def sample_job_below_threshold() -> dict:
    """A job with match score below 80%."""
    return {
        "id": "job-99999",
        "title": "Junior Frontend Developer",
        "company": "WebShop",
        "location": "Mumbai, India",
        "is_external": False,
        "match_score": 0.60,
        "matched_qualifications": 3,
        "required_qualifications": 5,
        "description": "Entry-level frontend position...",
        "recruiter": "Vikram Singh",
    }


@pytest.fixture
def sample_job_external() -> dict:
    """A job that uses external apply."""
    return {
        "id": "job-55555",
        "title": "Data Scientist",
        "company": "BigCo",
        "location": "Hyderabad, India",
        "is_external": True,
        "match_score": 0.92,
        "matched_qualifications": 11,
        "required_qualifications": 12,
        "description": "Data scientist role...",
        "recruiter": "John Doe",
    }


# ---------------------------------------------------------------------------
# Fixtures: Config YAML file
# ---------------------------------------------------------------------------


@pytest.fixture
def config_yaml_file(tmp_path) -> Path:
    """Create a temporary config.yaml for testing config loading."""
    config_content = """\
candidate:
  name: "Test User"
  email: "test@example.com"
  phone: "+910000000000"
  resume_filename: "test_resume.pdf"
  notice_period: "Immediate"
  willing_to_relocate: true
  work_authorization: "Authorized to work"
  preferred_cities:
    - "Bangalore"

job_search:
  match_threshold: 0.75
  max_postings_per_run: 10
  collection: "Recommended"
  skip_external_apply: true

scheduler:
  interval_minutes: 30
  active_hours_start: 10
  active_hours_end: 20

telegram:
  notify_on_submit: true
  notify_on_pause: true
  notify_on_skip: true
  tally_interval_minutes: 15

inmail:
  enabled: false
  tone: "casual"
  max_length: 200
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)
    return config_path

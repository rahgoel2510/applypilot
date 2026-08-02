"""Tests for external application handler."""

import pytest

from linkedin_agent.external_apply import detect_ats, ExternalApplicant


class TestDetectATS:
    """Tests for ATS platform detection."""

    def test_greenhouse(self):
        assert detect_ats("https://boards.greenhouse.io/company/jobs/123") == "greenhouse"
        assert detect_ats("https://greenhouse.io/apply/456") == "greenhouse"

    def test_lever(self):
        assert detect_ats("https://jobs.lever.co/company/position") == "lever"

    def test_workday(self):
        assert detect_ats("https://company.myworkdayjobs.com/en-US/job/123") == "workday"

    def test_ashby(self):
        assert detect_ats("https://jobs.ashbyhq.com/company/role") == "ashby"

    def test_smartrecruiters(self):
        assert detect_ats("https://jobs.smartrecruiters.com/Corp/id") == "smartrecruiters"

    def test_unknown_platform(self):
        assert detect_ats("https://company.com/careers/apply") is None
        assert detect_ats("https://example.org/jobs") is None

    def test_case_insensitive(self):
        assert detect_ats("https://BOARDS.GREENHOUSE.IO/company") == "greenhouse"

    def test_empty_url(self):
        assert detect_ats("") is None


class TestExternalApplicantInit:
    """Tests for ExternalApplicant initialization."""

    def test_creates_with_page_and_candidate(self):
        from unittest.mock import MagicMock
        page = MagicMock()
        candidate = {"name": "Test", "resume_filename": "resume.pdf"}
        applicant = ExternalApplicant(page, candidate)
        assert applicant.page is page
        assert applicant.candidate == candidate

    def test_resume_path_search(self, tmp_path):
        from unittest.mock import MagicMock, patch
        page = MagicMock()
        resume_file = tmp_path / "resumes" / "test.pdf"
        resume_file.parent.mkdir()
        resume_file.touch()

        candidate = {"resume_filename": "test.pdf"}
        with patch("linkedin_agent.external_apply.Path.cwd", return_value=tmp_path):
            applicant = ExternalApplicant(page, candidate)
            assert applicant.resume_path == resume_file

    def test_missing_resume_returns_none(self):
        from unittest.mock import MagicMock
        page = MagicMock()
        candidate = {"resume_filename": "nonexistent_file_xyz.pdf"}
        applicant = ExternalApplicant(page, candidate)
        assert applicant.resume_path is None

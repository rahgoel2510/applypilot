"""Tests for the logging and ApplicationLogger module."""

import logging

import pytest

from linkedin_agent.logger import (
    ApplicationLogger,
    ApplicationResult,
    ResultStatus,
    setup_logging,
)


class TestResultStatus:
    """Tests for ResultStatus enum."""

    def test_submitted(self):
        assert ResultStatus.SUBMITTED == "submitted"

    def test_paused(self):
        assert ResultStatus.PAUSED == "paused"

    def test_skipped_threshold(self):
        assert ResultStatus.SKIPPED_THRESHOLD == "skipped_threshold"

    def test_skipped_external(self):
        assert ResultStatus.SKIPPED_EXTERNAL == "skipped_external"

    def test_is_string(self):
        assert isinstance(ResultStatus.SUBMITTED, str)


class TestApplicationResult:
    """Tests for the ApplicationResult dataclass."""

    def test_create_result(self):
        r = ApplicationResult(
            status=ResultStatus.SUBMITTED,
            company="Google",
            title="SWE",
            location="Bangalore",
            match_score=0.9,
        )
        assert r.status == ResultStatus.SUBMITTED
        assert r.company == "Google"
        assert r.match_score == 0.9
        assert r.timestamp is not None

    def test_optional_fields(self):
        r = ApplicationResult(
            status=ResultStatus.PAUSED,
            company="Meta",
            title="PM",
            location="Remote",
        )
        assert r.match_score is None
        assert r.blocking_fields is None


class TestSetupLogging:
    """Tests for the logging configuration."""

    def test_returns_logger(self):
        log = setup_logging(level="DEBUG")
        assert isinstance(log, logging.Logger)

    def test_info_level(self):
        log = setup_logging(level="INFO")
        assert log is not None

    def test_warning_level(self):
        log = setup_logging(level="WARNING")
        assert log is not None


class TestApplicationLogger:
    """Tests for the 4-bucket tally tracker."""

    def test_initial_empty(self):
        logger = ApplicationLogger()
        tally = logger.get_tally()
        assert tally["submitted"]["count"] == 0
        assert tally["paused"]["count"] == 0
        assert tally["skipped_threshold"]["count"] == 0
        assert tally["skipped_external"]["count"] == 0

    def test_log_submitted(self):
        logger = ApplicationLogger()
        result = ApplicationResult(
            status=ResultStatus.SUBMITTED,
            company="Google",
            title="SWE",
            location="Bangalore",
            match_score=0.9,
        )
        logger.log_result(result)
        assert logger.get_tally()["submitted"]["count"] == 1

    def test_log_paused(self):
        logger = ApplicationLogger()
        result = ApplicationResult(
            status=ResultStatus.PAUSED,
            company="Meta",
            title="PM",
            location="Remote",
            blocking_fields=["salary"],
        )
        logger.log_result(result)
        assert logger.get_tally()["paused"]["count"] == 1

    def test_log_skipped_threshold(self):
        logger = ApplicationLogger()
        result = ApplicationResult(
            status=ResultStatus.SKIPPED_THRESHOLD,
            company="Startup",
            title="Jr Dev",
            location="Mumbai",
            match_score=0.3,
        )
        logger.log_result(result)
        assert logger.get_tally()["skipped_threshold"]["count"] == 1

    def test_log_skipped_external(self):
        logger = ApplicationLogger()
        result = ApplicationResult(
            status=ResultStatus.SKIPPED_EXTERNAL,
            company="Corp",
            title="Lead",
            location="Delhi",
        )
        logger.log_result(result)
        assert logger.get_tally()["skipped_external"]["count"] == 1

    def test_multiple_entries(self):
        logger = ApplicationLogger()
        for _ in range(3):
            result = ApplicationResult(
                status=ResultStatus.SUBMITTED,
                company="Co",
                title="Dev",
                location="X",
            )
            logger.log_result(result)
        assert logger.get_tally()["submitted"]["count"] == 3

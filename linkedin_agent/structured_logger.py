"""Structured logging with correlation IDs for ApplyPilot.

Usage:
    from linkedin_agent.structured_logger import get_logger, cycle_context, job_context, configure_logging
    
    configure_logging()  # Call once at startup
    logger = get_logger(__name__)
    
    with cycle_context():
        logger.info("scan_started", max_postings=50)
        with job_context(job_id="abc123", title="SWE", company="Google"):
            logger.info("job_processing", match_score=0.85)
"""

import logging
import os
import sys
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

import structlog

# ---------------------------------------------------------------------------
# Context Variables for Correlation IDs
# ---------------------------------------------------------------------------

_cycle_id: ContextVar[str] = ContextVar("cycle_id", default="")
_job_id: ContextVar[str] = ContextVar("job_id", default="")
_job_title: ContextVar[str] = ContextVar("job_title", default="")
_job_company: ContextVar[str] = ContextVar("job_company", default="")
_agent_id: ContextVar[str] = ContextVar("agent_id", default="")


@contextmanager
def cycle_context(cycle_id: str | None = None):
    """Set cycle_id in structured logging context for the duration of a scan cycle."""
    cid = cycle_id or uuid.uuid4().hex[:12]
    token = _cycle_id.set(cid)
    try:
        yield cid
    finally:
        _cycle_id.reset(token)


@contextmanager
def job_context(job_id: str, title: str = "", company: str = ""):
    """Set job context in structured logging context."""
    t1 = _job_id.set(job_id)
    t2 = _job_title.set(title)
    t3 = _job_company.set(company)
    try:
        yield
    finally:
        _job_id.reset(t1)
        _job_title.reset(t2)
        _job_company.reset(t3)


@contextmanager
def agent_context(agent_id: str):
    """Set agent_id in structured logging context."""
    token = _agent_id.set(agent_id)
    try:
        yield
    finally:
        _agent_id.reset(token)


# ---------------------------------------------------------------------------
# Custom Processors
# ---------------------------------------------------------------------------


def _add_correlation_ids(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject correlation IDs from context variables into log events."""
    cycle = _cycle_id.get("")
    job = _job_id.get("")
    title = _job_title.get("")
    company = _job_company.get("")
    agent = _agent_id.get("")

    if cycle:
        event_dict["cycle_id"] = cycle
    if job:
        event_dict["job_id"] = job
    if title:
        event_dict["job_title"] = title
    if company:
        event_dict["job_company"] = company
    if agent:
        event_dict["agent_id"] = agent

    return event_dict


def _add_service_info(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add static service metadata."""
    event_dict["service"] = "applypilot"
    return event_dict


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_configured = False


def configure_logging() -> None:
    """Configure structlog + stdlib logging integration.
    
    Call this once at application startup.
    Reads LOG_LEVEL and LOG_FORMAT from environment.
    """
    global _configured
    if _configured:
        return
    _configured = True

    log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    log_format = os.environ.get("LOG_FORMAT", "json").lower()
    is_json = log_format == "json"

    # Shared processors for both structlog and stdlib
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_correlation_ids,
        _add_service_info,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if is_json:
        # JSON output for production / log aggregation
        renderer = structlog.processors.JSONRenderer()
    else:
        # Colored console output for development
        renderer = structlog.dev.ConsoleRenderer(
            colors=sys.stderr.isatty(),
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog formatting
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silence noisy libraries
    for noisy in ("httpx", "httpcore", "urllib3", "playwright", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.
    
    Args:
        name: Usually __name__ of the calling module.
    
    Returns:
        A structlog BoundLogger with correlation ID support.
    """
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)

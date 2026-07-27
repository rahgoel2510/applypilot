"""SQLAlchemy models and Pydantic schemas for Job Application Tracker."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Enum, Float, String, Text
from sqlalchemy.dialects.sqlite import CHAR

from database import Base


# --- Enums ---

class JobStage(str, enum.Enum):
    saved = "saved"
    applied = "applied"
    interviewing = "interviewing"
    offered = "offered"
    rejected = "rejected"


class JobSource(str, enum.Enum):
    manual = "manual"
    agent = "agent"


class AgentEvent(str, enum.Enum):
    submitted = "submitted"
    paused = "paused"
    skipped = "skipped"


# Event-to-stage mapping
EVENT_STAGE_MAP = {
    AgentEvent.submitted: JobStage.applied,
    AgentEvent.paused: JobStage.saved,
    AgentEvent.skipped: JobStage.saved,
}


# --- SQLAlchemy Model ---

class Job(Base):
    __tablename__ = "jobs"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=True)
    date_added = Column(DateTime, default=datetime.utcnow, nullable=False)
    stage = Column(Enum(JobStage), default=JobStage.saved, nullable=False)
    posting_url = Column(String, nullable=True)
    match_score = Column(Float, nullable=True)
    source = Column(Enum(JobSource), default=JobSource.manual, nullable=False)
    notes = Column(Text, nullable=True)


# --- Pydantic Schemas ---

class JobBase(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    stage: JobStage = JobStage.saved
    posting_url: Optional[str] = None
    match_score: Optional[float] = None
    source: JobSource = JobSource.manual
    notes: Optional[str] = None


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    stage: Optional[JobStage] = None
    posting_url: Optional[str] = None
    match_score: Optional[float] = None
    source: Optional[JobSource] = None
    notes: Optional[str] = None


class JobResponse(JobBase):
    id: str
    date_added: datetime

    class Config:
        from_attributes = True


class StageUpdate(BaseModel):
    stage: JobStage


class WebhookPayload(BaseModel):
    event: AgentEvent
    title: str
    company: str
    location: Optional[str] = None
    match_score: Optional[float] = None
    posting_url: Optional[str] = None


class StatsResponse(BaseModel):
    saved: int = 0
    applied: int = 0
    interviewing: int = 0
    offered: int = 0
    rejected: int = 0
    total: int = 0


# ===========================================================================
# Activity Log — captures every agent trigger, action, error, lifecycle event
# ===========================================================================


class LogSeverity(str, enum.Enum):
    info = "info"
    success = "success"
    warning = "warning"
    error = "error"


class LogEventType(str, enum.Enum):
    # Agent lifecycle
    agent_start = "agent_start"
    agent_stop = "agent_stop"
    cycle_start = "cycle_start"
    cycle_end = "cycle_end"
    # Job processing
    job_submitted = "job_submitted"
    job_paused = "job_paused"
    job_skipped = "job_skipped"
    job_error = "job_error"
    # InMail
    inmail_drafted = "inmail_drafted"
    inmail_sent = "inmail_sent"
    # Telegram
    telegram_sent = "telegram_sent"
    human_input_requested = "human_input_requested"
    human_input_received = "human_input_received"
    # System
    error = "error"
    warning = "warning"
    info = "info"


# --- SQLAlchemy Model ---

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_type = Column(Enum(LogEventType), nullable=False, index=True)
    severity = Column(Enum(LogSeverity), default=LogSeverity.info, nullable=False)
    title = Column(String, nullable=True)       # Job title (if related to a job)
    company = Column(String, nullable=True)     # Company (if related to a job)
    stage = Column(String, nullable=True)       # Stage at time of event
    message = Column(Text, nullable=False)      # Human-readable event description
    metadata_json = Column(Text, nullable=True) # Extra data as JSON string


# --- Settings stored in DB ---

class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentRun(Base):
    """Persists every agent run with its config, outcome, and logs."""
    __tablename__ = "agent_runs"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String, default="running", nullable=False)  # running, completed, failed, stopped
    mode = Column(String, nullable=False)  # single, daemon
    dry_run = Column(String, default="true")
    limit = Column(String, nullable=True)
    match_threshold = Column(String, nullable=True)
    collection = Column(String, nullable=True)
    # Results
    jobs_processed = Column(String, default="0")
    jobs_applied = Column(String, default="0")
    jobs_skipped = Column(String, default="0")
    jobs_paused = Column(String, default="0")
    jobs_errored = Column(String, default="0")
    duration_seconds = Column(String, default="0")
    # Logs
    output_log = Column(Text, default="")  # Full stdout capture
    error_message = Column(Text, nullable=True)


# --- Pydantic Schemas ---

class LogCreate(BaseModel):
    event_type: LogEventType
    severity: LogSeverity = LogSeverity.info
    title: Optional[str] = None
    company: Optional[str] = None
    stage: Optional[str] = None
    message: str
    metadata_json: Optional[str] = None


class LogResponse(BaseModel):
    id: str
    timestamp: datetime
    event_type: LogEventType
    severity: LogSeverity
    title: Optional[str] = None
    company: Optional[str] = None
    stage: Optional[str] = None
    message: str
    metadata_json: Optional[str] = None

    class Config:
        from_attributes = True


class LogsPageResponse(BaseModel):
    logs: list[LogResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

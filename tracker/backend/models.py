"""SQLAlchemy models and Pydantic schemas for Job Application Tracker."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.sqlite import CHAR

from database import Base


# --- Enums ---

class JobStage(str, enum.Enum):
    discovered = "discovered"
    reached_out = "reached_out"
    saved = "saved"
    applied = "applied"
    interviewing = "interviewing"
    offered = "offered"
    rejected = "rejected"


class JobSource(str, enum.Enum):
    manual = "manual"
    agent = "agent"


class AgentEvent(str, enum.Enum):
    discovered = "discovered"
    reached_out = "reached_out"
    submitted = "submitted"
    paused = "paused"
    skipped = "skipped"


# Event-to-stage mapping
EVENT_STAGE_MAP = {
    AgentEvent.discovered: JobStage.discovered,
    AgentEvent.reached_out: JobStage.reached_out,
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
    discovered: int = 0
    reached_out: int = 0
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


# ===========================================================================
# InMail Drafts — persists AI-generated InMail messages linked to jobs
# ===========================================================================


class InMailDraftStatus(str, enum.Enum):
    drafted = "drafted"
    sent = "sent"
    skipped = "skipped"


class InMailDraft(Base):
    __tablename__ = "inmail_drafts"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(CHAR(36), ForeignKey("jobs.id"), nullable=True)
    job_title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    recruiter_name = Column(String, nullable=False)
    draft_text = Column(Text, nullable=False)
    status = Column(Enum(InMailDraftStatus), default=InMailDraftStatus.drafted, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


# --- InMail Draft Pydantic Schemas ---


class InMailDraftCreate(BaseModel):
    job_id: Optional[str] = None
    job_title: str
    company: str
    recruiter_name: str
    draft_text: str
    status: InMailDraftStatus = InMailDraftStatus.drafted


class InMailDraftResponse(BaseModel):
    id: str
    job_id: Optional[str] = None
    job_title: str
    company: str
    recruiter_name: str
    draft_text: str
    status: InMailDraftStatus
    created_at: datetime

    class Config:
        from_attributes = True


class InMailDraftStatusUpdate(BaseModel):
    status: InMailDraftStatus


# --- Pydantic Schemas ---

# ===========================================================================
# Feedback Signal — captures user actions for self-learning scoring loop
# ===========================================================================


class FeedbackSignal(Base):
    __tablename__ = "feedback_signals"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(CHAR(36), nullable=False, index=True)  # FK to jobs.id (logical)
    job_title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    original_score = Column(Float, nullable=True)
    user_action = Column(String, nullable=False)  # e.g. 'promoted_to_interview', 'rejected', 'manual_apply'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class FeedbackSignalResponse(BaseModel):
    id: str
    job_id: str
    job_title: str
    company: str
    original_score: Optional[float] = None
    user_action: str
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackSummaryResponse(BaseModel):
    total_signals: dict[str, int]  # action -> count
    avg_score_by_action: dict[str, Optional[float]]  # action -> avg original_score
    promoted_companies: list[str]  # companies consistently promoted
    rejected_companies: list[str]  # companies consistently rejected


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


# ===========================================================================
# TODO / Notifications — actionable items for the user
# ===========================================================================


class TodoPriority(str, enum.Enum):
    high = 'high'
    medium = 'medium'
    low = 'low'


class TodoStatus(str, enum.Enum):
    pending = 'pending'
    done = 'done'
    dismissed = 'dismissed'


class Todo(Base):
    __tablename__ = 'todos'

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False)  # 'external_apply', 'review_inmail', 'skill_gap', 'session_refresh', 'agent_error'
    priority = Column(Enum(TodoPriority), default=TodoPriority.medium)
    status = Column(Enum(TodoStatus), default=TodoStatus.pending)
    job_id = Column(String, nullable=True)  # Link to job if relevant
    job_title = Column(String, nullable=True)
    company = Column(String, nullable=True)
    action_url = Column(String, nullable=True)  # External apply link, etc
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    reminder_at = Column(DateTime, nullable=True)
    metadata_json = Column(Text, nullable=True)


# --- Todo Pydantic Schemas ---


class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: str
    priority: TodoPriority = TodoPriority.medium
    job_id: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    action_url: Optional[str] = None
    reminder_at: Optional[datetime] = None
    metadata_json: Optional[str] = None


class TodoAutoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: str
    priority: TodoPriority = TodoPriority.medium
    job_id: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    action_url: Optional[str] = None
    reminder_at: Optional[datetime] = None
    metadata_json: Optional[str] = None


class TodoUpdate(BaseModel):
    status: Optional[TodoStatus] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TodoPriority] = None
    reminder_at: Optional[datetime] = None


class TodoResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    category: str
    priority: TodoPriority
    status: TodoStatus
    job_id: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    action_url: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    reminder_at: Optional[datetime] = None
    metadata_json: Optional[str] = None

    class Config:
        from_attributes = True


class TodoCountResponse(BaseModel):
    pending_count: int

"""Event types and data models for the pipeline."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


class EventType(str, Enum):
    """Pipeline event types (topics)."""
    JOB_DISCOVERED = "job.discovered"
    JOB_EVALUATED = "job.evaluated"
    JOB_QUALIFIED = "job.qualified"
    JOB_DISQUALIFIED = "job.disqualified"
    JOB_APPLYING = "job.applying"
    JOB_APPLIED = "job.applied"
    JOB_FAILED = "job.failed"
    JOB_PAUSED = "job.paused"
    JOB_RETRYING = "job.retrying"
    JOB_EXTERNAL = "job.external"
    CYCLE_STARTED = "cycle.started"
    CYCLE_COMPLETED = "cycle.completed"
    CHALLENGE_DETECTED = "challenge.detected"
    CHALLENGE_RESOLVED = "challenge.resolved"
    CAP_REACHED = "cap.reached"


class Platform(str, Enum):
    """Supported job platforms."""
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    NAUKRI = "naukri"
    WELLFOUND = "wellfound"
    GREENHOUSE = "greenhouse"


@dataclass
class StageMarker:
    """Records when a job passed through a pipeline stage.
    
    Like a Kafka offset — tells you exactly where this job is
    in the pipeline and what happened at each stage.
    """
    stage: str
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "completed"  # completed, failed, skipped
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


@dataclass
class JobEvent:
    """A single event in the pipeline — the unit of work.
    
    Carries all context needed by any stage to process the job.
    Stage markers accumulate as the job flows through the pipeline.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: EventType = EventType.JOB_DISCOVERED
    platform: Platform = Platform.LINKEDIN
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Job data
    job_id: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""
    description: str = ""
    is_easy_apply: bool = True
    external_url: str | None = None
    
    # Scoring
    match_score: float | None = None
    scoring_method: str = ""  # premium, fallback, manual
    
    # Stage markers (append-only log of what happened)
    stage_markers: list[StageMarker] = field(default_factory=list)
    
    # Metadata (extensible)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Error tracking
    error: str | None = None
    retry_count: int = 0

    def add_marker(self, stage: str, status: str = "completed", duration_ms: int = 0, **kwargs) -> None:
        """Add a stage marker to this event's history."""
        self.stage_markers.append(StageMarker(
            stage=stage, status=status, duration_ms=duration_ms, metadata=kwargs
        ))

    @property
    def current_stage(self) -> str:
        """Return the most recent stage this event passed through."""
        return self.stage_markers[-1].stage if self.stage_markers else "created"

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "platform": self.platform.value,
            "timestamp": self.timestamp.isoformat(),
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "match_score": self.match_score,
            "scoring_method": self.scoring_method,
            "stage_markers": [m.to_dict() for m in self.stage_markers],
            "error": self.error,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }

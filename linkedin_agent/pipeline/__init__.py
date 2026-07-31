"""Event-driven pipeline architecture for multi-platform job application.

Kafka-inspired design:
- Events flow through topics (EventType)
- Stages are independent consumers/producers
- Stage markers track progress (like consumer offsets)
- Dead-letter queue for failed events
- Platform adapters produce discovery events

Usage:
    from linkedin_agent.pipeline import EventBus, JobEvent, EventType
    
    bus = EventBus()
    # Register stages...
    await bus.publish(JobEvent(event_type=EventType.CYCLE_STARTED))
"""
from .events import EventType, JobEvent, Platform, StageMarker
from .bus import EventBus
from .stages import (
    PipelineStage,
    DiscoveryStage,
    EvaluationStage,
    ApplicationStage,
    NotificationStage,
)

__all__ = [
    "EventType",
    "JobEvent",
    "Platform",
    "StageMarker",
    "EventBus",
    "PipelineStage",
    "DiscoveryStage",
    "EvaluationStage",
    "ApplicationStage",
    "NotificationStage",
]

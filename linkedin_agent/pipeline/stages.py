"""Pipeline stage definitions — independent processors that subscribe to events.

Each stage is a self-contained unit that:
- Subscribes to specific event types (input topics)
- Processes events and produces new events (output topics)
- Can be enabled/disabled independently
- Reports its own metrics
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from .events import EventType, JobEvent, Platform
from .bus import EventBus

logger = logging.getLogger(__name__)


class PipelineStage(ABC):
    """Base class for all pipeline stages.
    
    A stage is an independent event processor. It:
    - Subscribes to input event types
    - Processes events
    - Publishes output events
    """

    name: str = "base_stage"
    input_events: list[EventType] = []
    output_events: list[EventType] = []

    def __init__(self, bus: EventBus, config: dict[str, Any] | None = None) -> None:
        self.bus = bus
        self.config = config or {}
        self.enabled = True
        self._processed = 0
        self._errors = 0

        # Auto-subscribe to input events
        for event_type in self.input_events:
            self.bus.subscribe(event_type, self.handle)

        logger.info("Stage '%s' initialized (inputs: %s)", self.name, [e.value for e in self.input_events])

    @abstractmethod
    async def process(self, event: JobEvent) -> JobEvent | None:
        """Process an event and optionally produce a new event.
        
        Return a new JobEvent to publish it to the bus.
        Return None to stop propagation (event consumed).
        """
        ...

    async def handle(self, event: JobEvent) -> JobEvent | None:
        """Wrapper around process() that handles metrics and errors."""
        if not self.enabled:
            return event  # Pass through if disabled

        self._processed += 1
        t0 = time.time()

        try:
            result = await self.process(event)
            return result
        except Exception as exc:
            self._errors += 1
            logger.error("Stage '%s' error: %s", self.name, exc)
            event.add_marker(self.name, status="failed", error=str(exc)[:100])
            event.error = str(exc)[:200]
            event.event_type = EventType.JOB_FAILED
            return event

    @property
    def stats(self) -> dict[str, int]:
        return {
            "processed": self._processed,
            "errors": self._errors,
        }


class DiscoveryStage(PipelineStage):
    """Base discovery stage — platform adapters extend this.
    
    Discovers jobs from a platform and publishes JOB_DISCOVERED events.
    Each platform (LinkedIn, Indeed, Naukri) implements its own discoverer.
    """
    name = "discovery"
    input_events = [EventType.CYCLE_STARTED]
    output_events = [EventType.JOB_DISCOVERED]

    @abstractmethod
    async def discover_jobs(self, config: dict) -> list[JobEvent]:
        """Platform-specific job discovery. Override in subclasses."""
        ...

    async def process(self, event: JobEvent) -> JobEvent | None:
        """On CYCLE_STARTED, discover jobs and publish each as JOB_DISCOVERED."""
        jobs = await self.discover_jobs(self.config)
        for job_event in jobs:
            job_event.event_type = EventType.JOB_DISCOVERED
            job_event.add_marker("discovered", status="completed", platform=job_event.platform.value)
            await self.bus.publish(job_event)
        return None  # Don't propagate the cycle event further


class EvaluationStage(PipelineStage):
    """Scores and filters jobs. Platform-agnostic."""
    name = "evaluation"
    input_events = [EventType.JOB_DISCOVERED]
    output_events = [EventType.JOB_QUALIFIED, EventType.JOB_DISQUALIFIED, EventType.JOB_EXTERNAL]

    @abstractmethod
    async def evaluate(self, event: JobEvent) -> JobEvent:
        """Score the job and set event_type to QUALIFIED/DISQUALIFIED/EXTERNAL."""
        ...

    async def process(self, event: JobEvent) -> JobEvent | None:
        return await self.evaluate(event)


class ApplicationStage(PipelineStage):
    """Applies to qualified jobs. Platform-specific."""
    name = "application"
    input_events = [EventType.JOB_QUALIFIED]
    output_events = [EventType.JOB_APPLIED, EventType.JOB_FAILED, EventType.JOB_PAUSED]

    @abstractmethod
    async def apply(self, event: JobEvent) -> JobEvent:
        """Submit application. Returns event with APPLIED/FAILED/PAUSED type."""
        ...

    async def process(self, event: JobEvent) -> JobEvent | None:
        return await self.apply(event)


class NotificationStage(PipelineStage):
    """Sends notifications. Subscribes to multiple event types."""
    name = "notification"
    input_events = [
        EventType.JOB_APPLIED,
        EventType.JOB_EXTERNAL,
        EventType.JOB_PAUSED,
        EventType.JOB_FAILED,
        EventType.CAP_REACHED,
    ]
    output_events = []  # Terminal stage

    @abstractmethod
    async def notify(self, event: JobEvent) -> None:
        """Send notification for this event."""
        ...

    async def process(self, event: JobEvent) -> JobEvent | None:
        await self.notify(event)
        return None  # Terminal — don't propagate

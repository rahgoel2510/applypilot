"""Event bus — in-process message broker with persistence and stage routing.

Design:
- Topics are like Kafka topics (one per EventType)
- Handlers subscribe to topics
- Events are persisted to disk for crash recovery
- Stage markers provide full audit trail
- Supports both sync and async handlers
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Awaitable

from .events import EventType, JobEvent, Platform, StageMarker

logger = logging.getLogger(__name__)

# Type for event handlers
EventHandler = Callable[[JobEvent], Awaitable[JobEvent | None]]


class EventBus:
    """In-process event bus with topic-based routing and persistence.
    
    Kafka-inspired design:
    - Events are published to topics (EventType)
    - Handlers subscribe to specific topics
    - Events flow through handlers in registration order
    - Stage markers track progress (like consumer offsets)
    - Failed events go to a dead-letter topic for retry
    - Events are persisted for crash recovery
    """

    def __init__(self, persist_dir: str | Path | None = None) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._middleware: list[EventHandler] = []
        self._dead_letter: list[JobEvent] = []
        self._event_log: list[JobEvent] = []
        self._persist_dir = Path(persist_dir) if persist_dir else (
            Path.home() / ".linkedin_agent" / "pipeline"
        )
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._stats: dict[str, int] = defaultdict(int)
        self._running = False

    # ─── Subscription ──────────────────────────────────

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for a specific event type (topic)."""
        self._handlers[event_type].append(handler)
        logger.debug("Subscribed %s to topic %s", handler.__name__, event_type.value)

    def use(self, middleware: EventHandler) -> None:
        """Add middleware that runs on ALL events before handlers."""
        self._middleware.append(middleware)

    # ─── Publishing ────────────────────────────────────

    async def publish(self, event: JobEvent) -> None:
        """Publish an event to its topic and trigger handlers."""
        self._stats[event.event_type.value] += 1
        self._event_log.append(event)

        # Run middleware first
        for mw in self._middleware:
            try:
                result = await mw(event)
                if result is None:
                    # Middleware filtered this event
                    return
                event = result
            except Exception as exc:
                logger.error("Middleware %s failed: %s", mw.__name__, exc)

        # Route to topic handlers
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                t0 = time.time()
                result = await handler(event)
                duration_ms = int((time.time() - t0) * 1000)
                
                if result is not None:
                    # Handler produced a new event — publish it
                    result.add_marker(
                        stage=handler.__name__,
                        status="completed",
                        duration_ms=duration_ms,
                    )
                    await self.publish(result)
                    
            except Exception as exc:
                logger.error(
                    "Handler %s failed for event %s: %s",
                    handler.__name__, event.event_id, exc,
                )
                event.error = str(exc)[:200]
                event.add_marker(
                    stage=handler.__name__,
                    status="failed",
                    error=str(exc)[:100],
                )
                self._dead_letter.append(event)

    async def publish_batch(self, events: list[JobEvent]) -> None:
        """Publish multiple events (e.g., all discovered jobs)."""
        for event in events:
            await self.publish(event)

    # ─── Dead Letter / Retry ───────────────────────────

    def get_dead_letter_events(self) -> list[JobEvent]:
        """Get events that failed processing."""
        return list(self._dead_letter)

    async def retry_dead_letters(self) -> int:
        """Retry all dead-letter events. Returns count of retried."""
        to_retry = self._dead_letter[:]
        self._dead_letter.clear()
        for event in to_retry:
            event.retry_count += 1
            event.error = None
            await self.publish(event)
        return len(to_retry)

    # ─── Persistence ───────────────────────────────────

    def save_state(self) -> None:
        """Persist current event log to disk for crash recovery."""
        state_file = self._persist_dir / "event_log.json"
        try:
            data = [e.to_dict() for e in self._event_log[-1000:]]  # Keep last 1000
            tmp = state_file.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2, default=str))
            tmp.replace(state_file)
        except Exception as exc:
            logger.warning("Failed to persist event log: %s", exc)

    # ─── Stats ─────────────────────────────────────────

    @property
    def stats(self) -> dict[str, int]:
        """Return event counts by type."""
        return dict(self._stats)

    @property
    def dead_letter_count(self) -> int:
        return len(self._dead_letter)

    @property
    def total_events(self) -> int:
        return len(self._event_log)

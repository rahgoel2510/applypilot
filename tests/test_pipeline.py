"""Tests for the event-driven pipeline architecture."""
import asyncio
import pytest
import tempfile
from pathlib import Path

from linkedin_agent.pipeline import (
    EventBus,
    EventType,
    JobEvent,
    Platform,
    StageMarker,
    PipelineStage,
    DiscoveryStage,
    EvaluationStage,
    ApplicationStage,
    NotificationStage,
)


# ─── Helpers ───────────────────────────────────────────


class MockEvaluationStage(EvaluationStage):
    """Concrete evaluation stage for testing."""

    async def evaluate(self, event: JobEvent) -> JobEvent:
        event.match_score = 0.85
        event.scoring_method = "mock"
        event.event_type = EventType.JOB_QUALIFIED
        return event


class MockNotificationStage(NotificationStage):
    """Concrete notification stage for testing."""

    def __init__(self, bus, config=None):
        super().__init__(bus, config)
        self.notifications: list[JobEvent] = []

    async def notify(self, event: JobEvent) -> None:
        self.notifications.append(event)


# ─── Tests: JobEvent ───────────────────────────────────


class TestJobEvent:
    def test_creation_defaults(self):
        """Test JobEvent creation with default values."""
        event = JobEvent()
        assert event.event_type == EventType.JOB_DISCOVERED
        assert event.platform == Platform.LINKEDIN
        assert event.job_id == ""
        assert event.match_score is None
        assert event.stage_markers == []
        assert event.error is None
        assert event.retry_count == 0
        assert len(event.event_id) == 8

    def test_creation_with_values(self):
        """Test JobEvent creation with specified values."""
        event = JobEvent(
            job_id="123",
            title="Senior Engineer",
            company="Google",
            location="Bengaluru",
            platform=Platform.NAUKRI,
            event_type=EventType.JOB_QUALIFIED,
            match_score=0.92,
        )
        assert event.job_id == "123"
        assert event.title == "Senior Engineer"
        assert event.company == "Google"
        assert event.platform == Platform.NAUKRI
        assert event.match_score == 0.92

    def test_add_marker(self):
        """Test adding stage markers to a JobEvent."""
        event = JobEvent(job_id="abc")
        event.add_marker("discovery", status="completed", duration_ms=150)
        event.add_marker("evaluation", status="completed", duration_ms=50, score=0.85)

        assert len(event.stage_markers) == 2
        assert event.stage_markers[0].stage == "discovery"
        assert event.stage_markers[0].duration_ms == 150
        assert event.stage_markers[1].stage == "evaluation"
        assert event.stage_markers[1].metadata == {"score": 0.85}

    def test_current_stage(self):
        """Test current_stage property."""
        event = JobEvent()
        assert event.current_stage == "created"

        event.add_marker("discovery")
        assert event.current_stage == "discovery"

        event.add_marker("evaluation")
        assert event.current_stage == "evaluation"

    def test_to_dict(self):
        """Test serialization to dict."""
        event = JobEvent(
            job_id="xyz",
            title="Backend Dev",
            company="Microsoft",
            match_score=0.78,
        )
        event.add_marker("discovery")

        d = event.to_dict()
        assert d["job_id"] == "xyz"
        assert d["title"] == "Backend Dev"
        assert d["company"] == "Microsoft"
        assert d["match_score"] == 0.78
        assert d["event_type"] == "job.discovered"
        assert d["platform"] == "linkedin"
        assert len(d["stage_markers"]) == 1
        assert d["stage_markers"][0]["stage"] == "discovery"


# ─── Tests: EventBus ──────────────────────────────────


class TestEventBus:
    @pytest.fixture
    def bus(self, tmp_path):
        """Create a bus with a temp persist dir."""
        return EventBus(persist_dir=tmp_path / "pipeline")

    @pytest.mark.asyncio
    async def test_publish_triggers_handler(self, bus):
        """Test that publishing an event triggers subscribed handlers."""
        received = []

        async def handler(event: JobEvent) -> JobEvent | None:
            received.append(event)
            return None

        bus.subscribe(EventType.JOB_DISCOVERED, handler)
        event = JobEvent(job_id="test1", event_type=EventType.JOB_DISCOVERED)
        await bus.publish(event)

        assert len(received) == 1
        assert received[0].job_id == "test1"

    @pytest.mark.asyncio
    async def test_handler_not_triggered_wrong_topic(self, bus):
        """Test that handlers on other topics are not triggered."""
        received = []

        async def handler(event: JobEvent) -> JobEvent | None:
            received.append(event)
            return None

        bus.subscribe(EventType.JOB_APPLIED, handler)
        event = JobEvent(job_id="test2", event_type=EventType.JOB_DISCOVERED)
        await bus.publish(event)

        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_dead_letter_on_handler_failure(self, bus):
        """Test that failed handlers put events in dead-letter queue."""

        async def bad_handler(event: JobEvent) -> JobEvent | None:
            raise ValueError("Something went wrong")

        bus.subscribe(EventType.JOB_DISCOVERED, bad_handler)
        event = JobEvent(job_id="fail1", event_type=EventType.JOB_DISCOVERED)
        await bus.publish(event)

        assert bus.dead_letter_count == 1
        dead = bus.get_dead_letter_events()
        assert dead[0].job_id == "fail1"
        assert "Something went wrong" in dead[0].error

    @pytest.mark.asyncio
    async def test_middleware_filtering(self, bus):
        """Test that middleware can filter events (return None stops processing)."""
        received = []

        async def block_middleware(event: JobEvent) -> JobEvent | None:
            if event.company == "BlockedCorp":
                return None  # Filter out
            return event

        async def handler(event: JobEvent) -> JobEvent | None:
            received.append(event)
            return None

        bus.use(block_middleware)
        bus.subscribe(EventType.JOB_DISCOVERED, handler)

        # This should be blocked
        await bus.publish(JobEvent(company="BlockedCorp", event_type=EventType.JOB_DISCOVERED))
        assert len(received) == 0

        # This should pass through
        await bus.publish(JobEvent(company="GoodCorp", event_type=EventType.JOB_DISCOVERED))
        assert len(received) == 1
        assert received[0].company == "GoodCorp"

    @pytest.mark.asyncio
    async def test_event_stats_counting(self, bus):
        """Test that stats track event counts by type."""
        async def noop(event: JobEvent) -> JobEvent | None:
            return None

        bus.subscribe(EventType.JOB_DISCOVERED, noop)

        await bus.publish(JobEvent(event_type=EventType.JOB_DISCOVERED))
        await bus.publish(JobEvent(event_type=EventType.JOB_DISCOVERED))
        await bus.publish(JobEvent(event_type=EventType.JOB_APPLIED))

        stats = bus.stats
        assert stats["job.discovered"] == 2
        assert stats["job.applied"] == 1
        assert bus.total_events == 3

    @pytest.mark.asyncio
    async def test_retry_dead_letters(self, bus):
        """Test retrying dead-letter events."""
        call_count = 0

        async def flaky_handler(event: JobEvent) -> JobEvent | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First call fails")
            return None

        bus.subscribe(EventType.JOB_DISCOVERED, flaky_handler)
        await bus.publish(JobEvent(event_type=EventType.JOB_DISCOVERED))

        assert bus.dead_letter_count == 1

        retried = await bus.retry_dead_letters()
        assert retried == 1
        assert bus.dead_letter_count == 0

    @pytest.mark.asyncio
    async def test_handler_output_publishes_new_event(self, bus):
        """Test that handler returning an event publishes it downstream."""
        applied_events = []

        async def qualify_handler(event: JobEvent) -> JobEvent | None:
            event.event_type = EventType.JOB_APPLIED
            event.match_score = 0.9
            return event

        async def applied_handler(event: JobEvent) -> JobEvent | None:
            applied_events.append(event)
            return None

        bus.subscribe(EventType.JOB_DISCOVERED, qualify_handler)
        bus.subscribe(EventType.JOB_APPLIED, applied_handler)

        await bus.publish(JobEvent(event_type=EventType.JOB_DISCOVERED, job_id="chain1"))

        assert len(applied_events) == 1
        assert applied_events[0].job_id == "chain1"
        assert applied_events[0].match_score == 0.9

    @pytest.mark.asyncio
    async def test_save_state(self, bus):
        """Test persisting event log to disk."""
        await bus.publish(JobEvent(event_type=EventType.JOB_DISCOVERED, job_id="persist1"))
        bus.save_state()

        state_file = bus._persist_dir / "event_log.json"
        assert state_file.exists()
        import json
        data = json.loads(state_file.read_text())
        assert len(data) == 1
        assert data[0]["job_id"] == "persist1"

    @pytest.mark.asyncio
    async def test_publish_batch(self, bus):
        """Test publishing multiple events in batch."""
        received = []

        async def handler(event: JobEvent) -> JobEvent | None:
            received.append(event)
            return None

        bus.subscribe(EventType.JOB_DISCOVERED, handler)

        events = [
            JobEvent(event_type=EventType.JOB_DISCOVERED, job_id=f"batch{i}")
            for i in range(5)
        ]
        await bus.publish_batch(events)

        assert len(received) == 5


# ─── Tests: PipelineStage ─────────────────────────────


class TestPipelineStage:
    @pytest.fixture
    def bus(self, tmp_path):
        return EventBus(persist_dir=tmp_path / "pipeline")

    @pytest.mark.asyncio
    async def test_auto_subscribes(self, bus):
        """Test that stages auto-subscribe to their input events."""
        stage = MockEvaluationStage(bus)

        # Verify handler is registered
        handlers = bus._handlers[EventType.JOB_DISCOVERED]
        assert len(handlers) == 1
        assert handlers[0] == stage.handle

    @pytest.mark.asyncio
    async def test_stage_processes_event(self, bus):
        """Test that a stage processes events from the bus."""
        stage = MockEvaluationStage(bus)
        applied_events = []

        async def capture(event: JobEvent) -> JobEvent | None:
            applied_events.append(event)
            return None

        bus.subscribe(EventType.JOB_QUALIFIED, capture)

        await bus.publish(JobEvent(
            event_type=EventType.JOB_DISCOVERED,
            job_id="stage_test",
            company="TestCorp",
        ))

        assert len(applied_events) == 1
        assert applied_events[0].match_score == 0.85
        assert applied_events[0].scoring_method == "mock"

    @pytest.mark.asyncio
    async def test_stage_disabled(self, bus):
        """Test that disabled stages pass events through unchanged."""
        stage = MockEvaluationStage(bus)
        stage.enabled = False

        results = []

        async def capture(event: JobEvent) -> JobEvent | None:
            results.append(event)
            return None

        # The handler returns the event unchanged when disabled,
        # which triggers downstream publish with a stage marker
        bus.subscribe(EventType.JOB_DISCOVERED, capture)

        event = JobEvent(event_type=EventType.JOB_DISCOVERED, job_id="disabled_test")
        # Directly call handle to test disabled behavior
        result = await stage.handle(event)
        assert result is not None  # passes through
        assert result.match_score is None  # not processed

    @pytest.mark.asyncio
    async def test_stage_stats(self, bus):
        """Test stage metrics tracking."""
        stage = MockEvaluationStage(bus)

        # Need to capture the qualified event to avoid unhandled propagation issues
        async def sink(event: JobEvent) -> JobEvent | None:
            return None

        bus.subscribe(EventType.JOB_QUALIFIED, sink)

        await bus.publish(JobEvent(event_type=EventType.JOB_DISCOVERED))
        await bus.publish(JobEvent(event_type=EventType.JOB_DISCOVERED))

        assert stage.stats["processed"] == 2
        assert stage.stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_notification_stage(self, bus):
        """Test that notification stage consumes events (terminal)."""
        stage = MockNotificationStage(bus)

        await bus.publish(JobEvent(event_type=EventType.JOB_APPLIED, job_id="notif1"))
        await bus.publish(JobEvent(event_type=EventType.JOB_EXTERNAL, job_id="notif2"))

        assert len(stage.notifications) == 2
        assert stage.notifications[0].job_id == "notif1"
        assert stage.notifications[1].job_id == "notif2"


# ─── Tests: StageMarker ───────────────────────────────


class TestStageMarker:
    def test_to_dict(self):
        """Test StageMarker serialization."""
        marker = StageMarker(stage="evaluation", status="completed", duration_ms=42)
        d = marker.to_dict()
        assert d["stage"] == "evaluation"
        assert d["status"] == "completed"
        assert d["duration_ms"] == 42
        assert "timestamp" in d


# ─── Tests: Platform enum ─────────────────────────────


class TestPlatform:
    def test_platform_values(self):
        """Test all platform enum values."""
        assert Platform.LINKEDIN.value == "linkedin"
        assert Platform.INDEED.value == "indeed"
        assert Platform.NAUKRI.value == "naukri"
        assert Platform.WELLFOUND.value == "wellfound"
        assert Platform.GREENHOUSE.value == "greenhouse"

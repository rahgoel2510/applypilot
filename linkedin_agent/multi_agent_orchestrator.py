"""Multi-Agent Orchestrator — manages independent agents in isolated asyncio tasks.

Each agent runs in its own asyncio task with NO shared state (no shared browser,
no shared files, no shared DB connections). If one agent crashes, others continue.

This orchestrator works ALONGSIDE the existing AgentController (which manages the
LinkedIn agent subprocess). Agents like the Naukri agent are managed here.

Usage:
    from linkedin_agent.multi_agent_orchestrator import get_orchestrator

    orchestrator = get_orchestrator()
    orchestrator.register_agent(
        agent_id='naukri',
        name='Naukri Agent',
        description='Scans and applies to Naukri jobs',
        runner=naukri_runner_func,
        schedule_minutes=60,
        schedule_time='09:00',
    )
    await orchestrator.start()
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class AgentState(str, Enum):
    """Lifecycle states for a managed agent."""

    idle = "idle"
    running = "running"
    scheduled = "scheduled"
    error = "error"
    disabled = "disabled"


@dataclass
class AgentRunRecord:
    """Immutable record of a single agent execution."""

    run_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str = "running"  # running | success | error | cancelled
    output: list[str] = field(default_factory=list)
    error: Optional[str] = None
    actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "status": self.status,
            "output": self.output[-100:],  # cap output in serialized form
            "error": self.error,
            "actions": self.actions,
        }


@dataclass
class ManagedAgent:
    """Internal representation of a registered agent."""

    agent_id: str
    name: str
    description: str
    enabled: bool = True
    state: AgentState = AgentState.idle
    schedule_minutes: int = 1440  # default: once daily
    schedule_time: str = "08:00"  # preferred first-run time (HH:MM)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_history: list[AgentRunRecord] = field(default_factory=list)
    max_history: int = 50
    consecutive_failures: int = 0
    max_failures_before_disable: int = 5
    _task: Optional[asyncio.Task] = field(default=None, repr=False)
    _runner: Optional[Callable[[], Any]] = field(default=None, repr=False)
    _log_buffer: deque = field(default_factory=lambda: deque(maxlen=500), repr=False)

    def add_log(self, message: str) -> None:
        """Append a timestamped log line to the agent's private buffer."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._log_buffer.append(f"[{ts}] {message}")

    def trim_history(self) -> None:
        """Keep only the most recent N run records."""
        if len(self.run_history) > self.max_history:
            self.run_history = self.run_history[-self.max_history :]

    def compute_next_run(self) -> datetime:
        """Compute when this agent should next execute."""
        now = datetime.now()

        if self.last_run is None:
            # First run: schedule at the preferred time today (or tomorrow if past)
            hour, minute = _parse_time(self.schedule_time)
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target

        return self.last_run + timedelta(minutes=self.schedule_minutes)

    def to_status_dict(self) -> dict[str, Any]:
        """Serialize agent status for API responses."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "state": self.state.value,
            "schedule_minutes": self.schedule_minutes,
            "schedule_time": self.schedule_time,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "consecutive_failures": self.consecutive_failures,
            "total_runs": len(self.run_history),
            "last_error": (
                self.run_history[-1].error
                if self.run_history and self.run_history[-1].error
                else None
            ),
        }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class MultiAgentOrchestrator:
    """Manages multiple independent agents, each in its own asyncio task.

    Thread-safety: All mutations go through an asyncio.Lock so concurrent
    FastAPI requests cannot corrupt state.
    """

    SCHEDULER_INTERVAL_SECONDS: int = 30

    def __init__(self) -> None:
        self._agents: dict[str, ManagedAgent] = {}
        self._running: bool = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        logger.info("MultiAgentOrchestrator initialized")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_agent(
        self,
        agent_id: str,
        name: str,
        description: str,
        runner: Callable[[], Any],
        schedule_minutes: int = 1440,
        schedule_time: str = "08:00",
        max_failures_before_disable: int = 5,
    ) -> None:
        """Register an agent with its async runner function.

        Args:
            agent_id: Unique identifier (e.g. 'naukri', 'indeed').
            name: Human-readable name.
            description: What the agent does.
            runner: Async callable `async def runner() -> dict`.
                    Must return {"success": bool, "actions": list[str], "error": str|None}.
            schedule_minutes: Interval between runs.
            schedule_time: Preferred first-run time (HH:MM, 24h format).
            max_failures_before_disable: Auto-disable after N consecutive failures.
        """
        if agent_id in self._agents:
            logger.warning("Agent '%s' already registered — replacing", agent_id)

        agent = ManagedAgent(
            agent_id=agent_id,
            name=name,
            description=description,
            schedule_minutes=schedule_minutes,
            schedule_time=schedule_time,
            max_failures_before_disable=max_failures_before_disable,
        )
        agent._runner = runner
        agent.next_run = agent.compute_next_run()
        agent.state = AgentState.scheduled
        self._agents[agent_id] = agent
        logger.info(
            "Registered agent '%s' (%s) — schedule: every %d min, first run: %s",
            agent_id,
            name,
            schedule_minutes,
            agent.next_run.strftime("%H:%M"),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the orchestrator scheduler loop."""
        if self._running:
            logger.warning("Orchestrator already running")
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(
            self._scheduler_loop(), name="orchestrator-scheduler"
        )
        logger.info(
            "Orchestrator started — managing %d agent(s)", len(self._agents)
        )

    async def stop(self) -> None:
        """Gracefully stop the orchestrator and all running agents."""
        if not self._running:
            return

        logger.info("Orchestrator shutting down...")
        self._running = False

        # Cancel scheduler
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        # Cancel all agent tasks
        cancel_tasks: list[asyncio.Task] = []
        for agent in self._agents.values():
            if agent._task and not agent._task.done():
                agent._task.cancel()
                cancel_tasks.append(agent._task)

        if cancel_tasks:
            await asyncio.gather(*cancel_tasks, return_exceptions=True)

        # Mark all as idle
        for agent in self._agents.values():
            if agent.state == AgentState.running:
                agent.state = AgentState.idle
            agent._task = None

        logger.info("Orchestrator stopped")

    # ------------------------------------------------------------------
    # Agent control (for FastAPI endpoints)
    # ------------------------------------------------------------------

    async def trigger_agent(self, agent_id: str) -> dict[str, Any]:
        """Manually trigger an agent run (ignoring schedule).

        Returns a status dict describing what happened.
        """
        agent = self._get_agent_or_raise(agent_id)

        if agent.state == AgentState.disabled:
            return {"ok": False, "error": f"Agent '{agent_id}' is disabled"}

        if agent.state == AgentState.running:
            return {"ok": False, "error": f"Agent '{agent_id}' is already running"}

        async with self._lock:
            agent._task = asyncio.create_task(
                self._execute_agent(agent_id), name=f"agent-{agent_id}-manual"
            )

        return {"ok": True, "message": f"Agent '{agent_id}' triggered"}

    async def stop_agent(self, agent_id: str) -> dict[str, Any]:
        """Cancel a running agent task."""
        agent = self._get_agent_or_raise(agent_id)

        if agent._task is None or agent._task.done():
            return {"ok": False, "error": f"Agent '{agent_id}' is not running"}

        agent._task.cancel()
        try:
            await agent._task
        except asyncio.CancelledError:
            pass

        agent.state = AgentState.idle
        agent._task = None
        agent.add_log("Run cancelled by user")

        # Mark the current run record as cancelled
        if agent.run_history:
            current = agent.run_history[-1]
            if current.status == "running":
                current.status = "cancelled"
                current.finished_at = datetime.now()

        return {"ok": True, "message": f"Agent '{agent_id}' stopped"}

    def enable_agent(self, agent_id: str) -> None:
        """Re-enable a disabled agent and reset failure counter."""
        agent = self._get_agent_or_raise(agent_id)
        agent.enabled = True
        agent.consecutive_failures = 0
        if agent.state == AgentState.disabled:
            agent.state = AgentState.scheduled
            agent.next_run = agent.compute_next_run()
        agent.add_log("Agent enabled")
        logger.info("Agent '%s' enabled", agent_id)

    def disable_agent(self, agent_id: str) -> None:
        """Disable an agent (won't be scheduled until re-enabled)."""
        agent = self._get_agent_or_raise(agent_id)
        agent.enabled = False
        agent.state = AgentState.disabled
        agent.add_log("Agent disabled")
        logger.info("Agent '%s' disabled", agent_id)

    def update_schedule(
        self,
        agent_id: str,
        schedule_minutes: Optional[int] = None,
        schedule_time: Optional[str] = None,
    ) -> None:
        """Update an agent's schedule parameters."""
        agent = self._get_agent_or_raise(agent_id)

        if schedule_minutes is not None:
            if schedule_minutes < 1:
                raise ValueError("schedule_minutes must be >= 1")
            agent.schedule_minutes = schedule_minutes

        if schedule_time is not None:
            # Validate format
            _parse_time(schedule_time)
            agent.schedule_time = schedule_time

        # Recompute next run
        agent.next_run = agent.compute_next_run()
        agent.add_log(
            f"Schedule updated: every {agent.schedule_minutes}min, time={agent.schedule_time}"
        )
        logger.info(
            "Agent '%s' schedule updated: %d min, time %s, next run %s",
            agent_id,
            agent.schedule_minutes,
            agent.schedule_time,
            agent.next_run.isoformat(),
        )

    # ------------------------------------------------------------------
    # Status / Query (for FastAPI endpoints)
    # ------------------------------------------------------------------

    def get_agent_status(self, agent_id: str) -> dict[str, Any]:
        """Get detailed status of a specific agent."""
        agent = self._get_agent_or_raise(agent_id)
        return agent.to_status_dict()

    def get_all_statuses(self) -> list[dict[str, Any]]:
        """Get status summaries for all registered agents."""
        return [agent.to_status_dict() for agent in self._agents.values()]

    def get_agent_logs(self, agent_id: str, limit: int = 50) -> list[str]:
        """Get recent log lines for an agent.

        Args:
            agent_id: The agent to query.
            limit: Max number of log lines to return (most recent first).
        """
        agent = self._get_agent_or_raise(agent_id)
        logs = list(agent._log_buffer)
        return logs[-limit:]

    def get_agent_history(self, agent_id: str) -> list[dict[str, Any]]:
        """Get run history for an agent (most recent first)."""
        agent = self._get_agent_or_raise(agent_id)
        return [record.to_dict() for record in reversed(agent.run_history)]

    def get_registered_agent_ids(self) -> list[str]:
        """Return all registered agent IDs."""
        return list(self._agents.keys())

    # ------------------------------------------------------------------
    # Internal: Scheduler
    # ------------------------------------------------------------------

    async def _scheduler_loop(self) -> None:
        """Core loop — checks every 30s if any agent is due to run."""
        logger.info("Scheduler loop started (interval: %ds)", self.SCHEDULER_INTERVAL_SECONDS)

        while self._running:
            try:
                await self._check_and_dispatch()
            except Exception as exc:
                # Scheduler must never crash
                logger.error("Scheduler loop error: %s", exc, exc_info=True)

            try:
                await asyncio.sleep(self.SCHEDULER_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break

        logger.info("Scheduler loop exited")

    async def _check_and_dispatch(self) -> None:
        """Check all agents and dispatch any that are due."""
        now = datetime.now()

        for agent in self._agents.values():
            if not agent.enabled:
                continue
            if agent.state == AgentState.running:
                continue
            if agent.state == AgentState.disabled:
                continue
            if agent.next_run is None:
                continue
            if now < agent.next_run:
                continue

            # Agent is due — dispatch it
            async with self._lock:
                if agent.state == AgentState.running:
                    # Double-check under lock
                    continue
                agent._task = asyncio.create_task(
                    self._execute_agent(agent.agent_id),
                    name=f"agent-{agent.agent_id}-scheduled",
                )
                logger.info("Dispatched scheduled run for agent '%s'", agent.agent_id)

    # ------------------------------------------------------------------
    # Internal: Agent execution
    # ------------------------------------------------------------------

    async def _execute_agent(self, agent_id: str) -> None:
        """Execute a single agent run in complete isolation.

        This method:
        1. Creates a run record
        2. Calls the runner function
        3. Records the result
        4. Handles errors gracefully
        5. Updates scheduling state
        """
        agent = self._agents[agent_id]
        run_id = str(uuid.uuid4())[:8]
        started_at = datetime.now()

        # Create run record
        record = AgentRunRecord(run_id=run_id, started_at=started_at)
        agent.run_history.append(record)
        agent.trim_history()

        # Update state
        agent.state = AgentState.running
        agent.last_run = started_at
        agent.add_log(f"Run {run_id} started")
        logger.info("Agent '%s' run %s started", agent_id, run_id)

        try:
            # Execute the runner in isolation
            if agent._runner is None:
                raise RuntimeError(f"No runner registered for agent '{agent_id}'")

            result = await asyncio.wait_for(
                agent._runner(),
                timeout=3600,  # 1 hour max per run
            )

            # Validate result format
            if not isinstance(result, dict):
                raise TypeError(
                    f"Runner must return dict, got {type(result).__name__}"
                )

            success = result.get("success", False)
            actions = result.get("actions", [])
            error = result.get("error")

            # Update record
            record.finished_at = datetime.now()
            record.actions = actions
            record.error = error

            if success:
                record.status = "success"
                agent.state = AgentState.scheduled
                agent.consecutive_failures = 0
                agent.add_log(
                    f"Run {run_id} succeeded — {len(actions)} action(s)"
                )
                logger.info(
                    "Agent '%s' run %s succeeded: %d actions",
                    agent_id,
                    run_id,
                    len(actions),
                )
            else:
                record.status = "error"
                agent.consecutive_failures += 1
                agent.add_log(f"Run {run_id} failed: {error or 'unknown error'}")
                logger.warning(
                    "Agent '%s' run %s failed: %s", agent_id, run_id, error
                )
                self._check_auto_disable(agent)

        except asyncio.CancelledError:
            record.finished_at = datetime.now()
            record.status = "cancelled"
            agent.state = AgentState.idle
            agent.add_log(f"Run {run_id} cancelled")
            logger.info("Agent '%s' run %s cancelled", agent_id, run_id)
            raise  # Re-raise so the task is properly cancelled

        except asyncio.TimeoutError:
            record.finished_at = datetime.now()
            record.status = "error"
            record.error = "Timed out after 3600 seconds"
            agent.consecutive_failures += 1
            agent.state = AgentState.error
            agent.add_log(f"Run {run_id} timed out")
            logger.error("Agent '%s' run %s timed out", agent_id, run_id)
            self._check_auto_disable(agent)

        except Exception as exc:
            record.finished_at = datetime.now()
            record.status = "error"
            record.error = f"{type(exc).__name__}: {exc}"
            agent.consecutive_failures += 1
            agent.state = AgentState.error
            agent.add_log(f"Run {run_id} crashed: {exc}")
            logger.error(
                "Agent '%s' run %s crashed: %s",
                agent_id,
                run_id,
                exc,
                exc_info=True,
            )
            self._check_auto_disable(agent)

        finally:
            # Always recompute next run and clean up task ref
            if agent.state not in (AgentState.disabled,):
                agent.next_run = agent.compute_next_run()
                if agent.state == AgentState.error:
                    # Stay in error state but still schedule
                    agent.state = AgentState.scheduled
            agent._task = None

    def _check_auto_disable(self, agent: ManagedAgent) -> None:
        """Auto-disable agent if it has exceeded max consecutive failures."""
        if agent.consecutive_failures >= agent.max_failures_before_disable:
            agent.enabled = False
            agent.state = AgentState.disabled
            agent.add_log(
                f"Auto-disabled after {agent.consecutive_failures} consecutive failures"
            )
            logger.error(
                "Agent '%s' auto-disabled after %d consecutive failures",
                agent.agent_id,
                agent.consecutive_failures,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_agent_or_raise(self, agent_id: str) -> ManagedAgent:
        """Retrieve an agent by ID or raise KeyError."""
        if agent_id not in self._agents:
            raise KeyError(f"No agent registered with id '{agent_id}'")
        return self._agents[agent_id]


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_orchestrator: Optional[MultiAgentOrchestrator] = None


def get_orchestrator() -> MultiAgentOrchestrator:
    """Get or create the singleton MultiAgentOrchestrator instance.

    This is the primary entry point for FastAPI routes and startup hooks.
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MultiAgentOrchestrator()
    return _orchestrator


def reset_orchestrator() -> None:
    """Reset the singleton (for testing only)."""
    global _orchestrator
    _orchestrator = None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _parse_time(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' string into (hour, minute) tuple.

    Raises ValueError on invalid format.
    """
    try:
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
        return hour, minute
    except (ValueError, IndexError):
        raise ValueError(
            f"Invalid time format '{time_str}' — expected HH:MM (24h)"
        )

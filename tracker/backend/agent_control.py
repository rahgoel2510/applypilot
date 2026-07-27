"""Agent process control — spawns/stops the LinkedIn agent from the tracker backend."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class AgentState(str, Enum):
    idle = "idle"
    running = "running"
    stopping = "stopping"
    error = "error"


@dataclass
class AgentStatus:
    state: AgentState = AgentState.idle
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    last_error: Optional[str] = None
    config: dict = field(default_factory=dict)
    # Running config
    mode: str = "idle"  # "single" or "daemon"
    dry_run: bool = False
    limit: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "pid": self.pid,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_error": self.last_error,
            "config": self.config,
            "mode": self.mode,
            "dry_run": self.dry_run,
            "limit": self.limit,
            "uptime_seconds": int((datetime.now() - self.started_at).total_seconds()) if self.started_at else 0,
        }


class AgentController:
    """Manages the LinkedIn agent as a subprocess."""

    def __init__(self):
        # Path to the project root (parent of tracker/)
        self._project_root = Path(__file__).resolve().parent.parent.parent
        self._process: Optional[subprocess.Popen] = None
        self._status = AgentStatus()
        self._output_lines: list[str] = []
        self._max_output = 500  # Keep last 500 lines
        self._lock = threading.Lock()

    @property
    def status(self) -> AgentStatus:
        # Check if process is still alive
        if self._process is not None:
            retcode = self._process.poll()
            if retcode is not None:
                # Process exited
                with self._lock:
                    if retcode == 0:
                        self._status.state = AgentState.idle
                    else:
                        self._status.state = AgentState.error
                        self._status.last_error = f"Process exited with code {retcode}"
                    self._status.pid = None
                    self._process = None
        return self._status

    @property
    def output(self) -> list[str]:
        with self._lock:
            return list(self._output_lines)

    def trigger(
        self,
        mode: str = "single",
        dry_run: bool = False,
        limit: Optional[int] = None,
        match_threshold: Optional[float] = None,
        collection: str = "Recommended",
    ) -> dict:
        """Start the agent.

        Args:
            mode: "single" for one scan cycle, "daemon" for continuous.
            dry_run: If True, scan but don't apply.
            limit: Max jobs to process (overrides config).
            match_threshold: Override match threshold (0.0-1.0).
            collection: Job collection to scan.

        Returns:
            Status dict.
        """
        if self._status.state == AgentState.running:
            return {"error": "Agent is already running", "status": self._status.to_dict()}

        # Build command
        python = sys.executable
        cmd = [python, "-m", "linkedin_agent"]

        if mode == "daemon":
            cmd.append("daemon")
        else:
            cmd.append("run")

        if dry_run:
            cmd.append("--dry-run")

        if limit is not None:
            cmd.extend(["--limit", str(limit)])

        # Environment (inherit current + load settings from DB)
        env = os.environ.copy()

        # Fetch settings from the tracker DB (live values, no restart needed)
        try:
            import httpx as _httpx
            resp = _httpx.get("http://127.0.0.1:8000/api/settings/env", timeout=5)
            if resp.status_code == 200:
                db_settings = resp.json()
                for key, value in db_settings.items():
                    if value:
                        env[key] = value
        except Exception:
            # Fallback: load from .env file if API unavailable
            env_file = self._project_root / ".env"
            if env_file.exists():
                from dotenv import dotenv_values
                for key, value in dotenv_values(env_file).items():
                    if value:
                        env[key] = value

        if match_threshold is not None:
            env["MATCH_THRESHOLD"] = str(match_threshold)

        # Start the process
        try:
            self._output_lines.clear()
            self._process = subprocess.Popen(
                cmd,
                cwd=str(self._project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )

            self._status = AgentStatus(
                state=AgentState.running,
                pid=self._process.pid,
                started_at=datetime.now(),
                mode=mode,
                dry_run=dry_run,
                limit=limit,
                config={
                    "collection": collection,
                    "match_threshold": match_threshold,
                    "dry_run": dry_run,
                    "limit": limit,
                    "mode": mode,
                },
            )

            # Start output reader thread
            reader = threading.Thread(target=self._read_output, daemon=True)
            reader.start()

            return {"message": "Agent started", "status": self._status.to_dict()}

        except Exception as exc:
            self._status.state = AgentState.error
            self._status.last_error = str(exc)
            return {"error": str(exc), "status": self._status.to_dict()}

    def stop(self) -> dict:
        """Stop the running agent."""
        if self._process is None or self._status.state != AgentState.running:
            return {"error": "Agent is not running", "status": self._status.to_dict()}

        self._status.state = AgentState.stopping
        try:
            # Send SIGTERM for graceful shutdown
            self._process.send_signal(signal.SIGTERM)

            # Wait up to 10 seconds
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill
                self._process.kill()
                self._process.wait(timeout=5)

            self._status.state = AgentState.idle
            self._status.pid = None
            self._process = None
            return {"message": "Agent stopped", "status": self._status.to_dict()}

        except Exception as exc:
            self._status.state = AgentState.error
            self._status.last_error = str(exc)
            return {"error": str(exc), "status": self._status.to_dict()}

    def _read_output(self) -> None:
        """Background thread: reads process stdout line by line."""
        if self._process is None or self._process.stdout is None:
            return
        try:
            for line in self._process.stdout:
                with self._lock:
                    self._output_lines.append(line.rstrip("\n"))
                    if len(self._output_lines) > self._max_output:
                        self._output_lines.pop(0)
        except (ValueError, OSError):
            pass  # Process closed


# Module-level singleton
_controller: Optional[AgentController] = None


def get_controller() -> AgentController:
    global _controller
    if _controller is None:
        _controller = AgentController()
    return _controller

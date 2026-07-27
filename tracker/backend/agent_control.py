"""Agent process control — spawns/stops the LinkedIn agent, persists run history."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import uuid
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
    mode: str = "idle"
    dry_run: bool = False
    limit: Optional[int] = None
    run_id: Optional[str] = None

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
            "run_id": self.run_id,
            "uptime_seconds": int((datetime.now() - self.started_at).total_seconds()) if self.started_at else 0,
        }


class AgentController:
    """Manages the LinkedIn agent as a subprocess and persists run history."""

    def __init__(self):
        self._project_root = Path(__file__).resolve().parent.parent.parent
        self._process: Optional[subprocess.Popen] = None
        self._status = AgentStatus()
        self._output_lines: list[str] = []
        self._max_output = 500
        self._lock = threading.Lock()

    @property
    def status(self) -> AgentStatus:
        if self._process is not None:
            retcode = self._process.poll()
            if retcode is not None:
                with self._lock:
                    if retcode == 0:
                        self._status.state = AgentState.idle
                        self._finalize_run("completed")
                    else:
                        self._status.state = AgentState.error
                        self._status.last_error = f"Process exited with code {retcode}"
                        self._finalize_run("failed", error=self._status.last_error)
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
        if self._status.state == AgentState.running:
            return {"error": "Agent is already running", "status": self._status.to_dict()}

        python = sys.executable
        cmd = [python, "-m", "linkedin_agent"]
        cmd.append("daemon" if mode == "daemon" else "run")
        if dry_run:
            cmd.append("--dry-run")
        if limit is not None:
            cmd.extend(["--limit", str(limit)])

        # Fetch settings from DB
        env = os.environ.copy()
        try:
            import httpx as _httpx
            resp = _httpx.get("http://127.0.0.1:8000/api/settings/env", timeout=5)
            if resp.status_code == 200:
                for key, value in resp.json().items():
                    if value:
                        env[key] = value
        except Exception:
            env_file = self._project_root / ".env"
            if env_file.exists():
                from dotenv import dotenv_values
                for key, value in dotenv_values(env_file).items():
                    if value:
                        env[key] = value

        if match_threshold is not None:
            env["MATCH_THRESHOLD"] = str(match_threshold)

        try:
            self._output_lines.clear()
            run_id = str(uuid.uuid4())

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
                run_id=run_id,
                config={
                    "collection": collection,
                    "match_threshold": match_threshold,
                    "dry_run": dry_run,
                    "limit": limit,
                    "mode": mode,
                },
            )

            # Persist run start in DB
            self._create_run_record(run_id, mode, dry_run, limit, match_threshold, collection)

            reader = threading.Thread(target=self._read_output, daemon=True)
            reader.start()

            return {"message": "Agent started", "status": self._status.to_dict()}

        except Exception as exc:
            self._status.state = AgentState.error
            self._status.last_error = str(exc)
            return {"error": str(exc), "status": self._status.to_dict()}

    def stop(self) -> dict:
        if self._process is None or self._status.state != AgentState.running:
            return {"error": "Agent is not running", "status": self._status.to_dict()}

        self._status.state = AgentState.stopping
        try:
            self._process.send_signal(signal.SIGTERM)
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)

            self._status.state = AgentState.idle
            self._status.pid = None
            self._process = None
            self._finalize_run("stopped")
            return {"message": "Agent stopped", "status": self._status.to_dict()}

        except Exception as exc:
            self._status.state = AgentState.error
            self._status.last_error = str(exc)
            return {"error": str(exc), "status": self._status.to_dict()}

    def _read_output(self) -> None:
        if self._process is None or self._process.stdout is None:
            return
        try:
            for line in self._process.stdout:
                with self._lock:
                    self._output_lines.append(line.rstrip("\n"))
                    if len(self._output_lines) > self._max_output:
                        self._output_lines.pop(0)
        except (ValueError, OSError):
            pass

    # ------------------------------------------------------------------
    # Run persistence
    # ------------------------------------------------------------------

    def _create_run_record(self, run_id, mode, dry_run, limit, threshold, collection):
        """Create an agent_runs record in DB."""
        try:
            from database import SessionLocal
            from models import AgentRun
            db = SessionLocal()
            run = AgentRun(
                id=run_id,
                started_at=datetime.now(),
                status="running",
                mode=mode,
                dry_run=str(dry_run),
                limit=str(limit) if limit else None,
                match_threshold=str(threshold) if threshold else None,
                collection=collection,
            )
            db.add(run)
            db.commit()
            db.close()
        except Exception:
            pass  # Non-critical — don't crash if DB write fails

    def _finalize_run(self, final_status: str, error: Optional[str] = None):
        """Update the run record with final status and logs."""
        run_id = self._status.run_id
        if not run_id:
            return
        try:
            from database import SessionLocal
            from models import AgentRun
            db = SessionLocal()
            run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if run:
                run.finished_at = datetime.now()
                run.status = final_status
                run.output_log = "\n".join(self._output_lines[-200:])  # Keep last 200 lines
                run.error_message = error
                if run.started_at:
                    run.duration_seconds = str(int((datetime.now() - run.started_at).total_seconds()))
                # Parse output for counts
                full_output = "\n".join(self._output_lines).lower()
                import re
                submitted = len(re.findall(r'(submitted|would apply)', full_output))
                skipped = len(re.findall(r'(skipping|would skip)', full_output))
                run.jobs_applied = str(submitted)
                run.jobs_skipped = str(skipped)
                processed = len(re.findall(r'processing:', full_output))
                run.jobs_processed = str(processed)
                db.commit()
            db.close()
        except Exception:
            pass


# Singleton
_controller: Optional[AgentController] = None


def get_controller() -> AgentController:
    global _controller
    if _controller is None:
        _controller = AgentController()
    return _controller

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
        search_mode: Optional[str] = None,
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
            _headers = {}
            _api_key = os.environ.get("APPLYPILOT_API_KEY", "")
            if _api_key:
                _headers["X-API-Key"] = _api_key
            resp = _httpx.get("http://127.0.0.1:8000/api/settings/env", timeout=5, headers=_headers)
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

        if search_mode is not None:
            env["SEARCH_MODE"] = search_mode

        # Enable verbose/debug output for full tech logs
        env["LOG_LEVEL"] = "DEBUG"
        env["PYTHONUNBUFFERED"] = "1"

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
        """Read subprocess stdout and transform into user-friendly messages."""
        if self._process is None or self._process.stdout is None:
            return
        try:
            in_traceback = False
            traceback_lines = []
            for line in self._process.stdout:
                clean_line = line.rstrip("\n")
                result = self._transform_line(clean_line, in_traceback, traceback_lines)

                if result == "__SKIP__":
                    continue
                elif result == "__TB_START__":
                    in_traceback = True
                    traceback_lines = [clean_line]
                    continue
                elif result == "__TB_ACC__":
                    traceback_lines.append(clean_line)
                    continue
                elif result == "__TB_END__":
                    traceback_lines.append(clean_line)
                    summary = self._summarize_traceback(traceback_lines)
                    in_traceback = False
                    traceback_lines = []
                    if summary:
                        with self._lock:
                            self._output_lines.append(summary)
                            if len(self._output_lines) > self._max_output:
                                self._output_lines.pop(0)
                    continue
                else:
                    in_traceback = False
                    traceback_lines = []
                    if result:
                        with self._lock:
                            self._output_lines.append(result)
                            if len(self._output_lines) > self._max_output:
                                self._output_lines.pop(0)
        except (ValueError, OSError):
            pass

    def _transform_line(self, line, in_traceback, traceback_lines):
        """Transform raw log line into user-friendly message."""
        import re
        s = line.strip()

        # Traceback handling
        if s.startswith(("\u256d\u2500", "\u2502 \u256d", "Traceback (most recent")):
            return "__TB_START__" if not in_traceback else "__TB_ACC__"
        if in_traceback:
            if re.match(r'^[A-Za-z_]*Error:', s) or re.match(r'^[A-Za-z_]*Exception:', s):
                return "__TB_END__"
            if s.startswith(("\u2502", "\u2570", "\u256d")):
                return "__TB_ACC__"
            if re.match(r'^\[?\d{2}/\d{2}/\d{2}', s):
                return "__TB_END__"
            return "__TB_ACC__"

        # Skip noise
        if not s or s.startswith(("\u256d", "\u2570", "\u2502")):
            return "__SKIP__"
        if re.match(r'^\s*(File |/Users/.*site-packages)', s):
            return "__SKIP__"

        # Detect Rich continuation lines (wrapped text from previous log message)
        # These are lines that DON'T start with a timestamp or level prefix
        # and the RAW line has heavy leading whitespace (Rich indents continuations)
        raw_leading = len(line) - len(line.lstrip())
        has_timestamp = bool(re.match(r'^\[?\d{2}/\d{2}/\d{2}', s))
        has_level = bool(re.match(r'^(INFO|WARNING|ERROR|DEBUG|CRITICAL)\s', s))
        is_continuation = raw_leading >= 20 and not has_timestamp and not has_level
        if is_continuation:
            # It's a wrapped fragment — skip unless it's one of our already-transformed messages
            if s.startswith(("\U0001f680", "\U0001f525", "\u26a1", "\U0001f310", "\u2705",
                           "\U0001f511", "\U0001f50d", "\U0001f4cb", "\U0001f50e",
                           "\U0001f4cd", "\U0001f4ca", "\U0001f9e0", "\U0001f3af",
                           "\U0001f517", "\U0001f44b", "\u26a0", "\u21b3", "\u274c",
                           "\u23ed", "\U0001f389", "\u23f8")):
                return s  # Already friendly, pass through
            return "__SKIP__"

        # Extract message from Rich format
        msg = re.sub(r'^\[?\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\]?\s*', '', s)
        msg = re.sub(r'^(INFO|WARNING|ERROR|DEBUG|CRITICAL)\s+', '', msg)
        msg = re.sub(r'\s+\w+\.py:\d+\s*$', '', msg)
        msg = re.sub(r'\s{3,}', '  ', msg).strip()
        if not msg:
            return "__SKIP__"

        # Humanize
        return self._humanize(msg)

    def _humanize(self, msg):
        """Convert log message to user-friendly narrative."""
        import re

        # Skip internal noise
        skip = [r'^Using user-agent:', r'^Browser launched \(headless',
                r'^Loaded \d+ cached', r'^Dedup DB connected', r'^AI model:',
                r'^Navigated to custom URL:', r'^Navigated to jobs collection:',
                r'^Searched jobs: keyword=', r'^Scan complete: \d+ unique',
                r'^Page \d+: scrolling', r'^Page \d+: \+\d+ jobs',
                r'^No new jobs on page', r'^No .Next. button', r'^Pagination ended',
                r'^Opened job \d+', r'^No Easy Apply', r"^'Show match details'",
                r'^Tally report sent:', r'^Notification sent:', r'^Across locations:',
                r'^Search efficiency:', r'^OR search already found',
                r'^Already seen \(dedup\):', r'^New discovered:',
                r'^Retry queue pending:', r'^Daily cap:', r'^Shutdown complete',
                r'^Browser closed', r'^Running single scan',
                r'^Search navigation attempt', r'^URL navigation attempt',
                r'^Collection navigation attempt',
                r'scanned\.$', r'reached\.$', r'^\d+ page\(s\)\.$',
                r'^page instead of', r'^scrape\.$',
                r'^failed:', r'^Call log:', r'^- navigatin',
                r'^\{.submitted', r'^https://', r'^posting',
                r'^data_dir=', r'^ication$', r'^Support/',
                r'^\(Macintosh', r'^AppleWebKit', r'^KHTML']
        for p in skip:
            if re.match(p, msg):
                return ""

        # Pipeline
        if msg == "Pipeline started":
            return "\U0001f680 Starting job search..."
        m = re.match(r'^Search mode: (\w+)', msg)
        if m:
            return f"\u26a1 Mode: {m.group(1).title()}"
        m = re.match(r'^URGENT MODE: max_postings=(\d+)', msg)
        if m:
            return f"\U0001f525 Urgent mode \u2014 scanning up to {m.group(1)} jobs"
        if "Launching browser" in msg:
            return "\U0001f310 Launching browser..."
        if re.match(r'^Browser ready', msg):
            return "\u2705 Browser ready"
        if "Checking LinkedIn session" in msg:
            return "\U0001f511 Checking your LinkedIn session..."
        if "Already logged in" in msg or "LinkedIn connected" in msg:
            return "\u2705 LinkedIn connected"
        if "Session expired" in msg:
            return "\u26a0\ufe0f Session expired \u2014 logging in..."

        # Discovery
        if "LinkedIn scanning started" in msg:
            return "\U0001f50d Scanning LinkedIn for jobs..."
        if "Checking Recommended" in msg:
            return "\U0001f4cb Checking Recommended jobs..."
        m = re.match(r"^Combined search \((.+?)\) .+ (\d+) jobs", msg)
        if m:
            return f"  \U0001f4cd {m.group(1)} \u2014 {m.group(2)} jobs" if m.group(2) != "0" else f"  \U0001f4cd {m.group(1)} \u2014 no new jobs"
        m = re.match(r"^'(.+?)' in (.+?) .+ (\d+) new jobs", msg)
        if m:
            return f"  \U0001f4cd {m.group(1)} in {m.group(2)} \u2014 {m.group(3)} jobs"
        if re.match(r"^Searching by keywords:", msg):
            return "\U0001f50e Searching across keywords & locations..."
        if re.match(r"^OR search found", msg):
            return ""
        m = re.match(r"^Found (\d+) unique jobs", msg)
        if m:
            return f"\U0001f4ca Found {m.group(1)} jobs to evaluate"
        m = re.match(r"^Dedup DB: (\d+)", msg)
        if m:
            return f"\U0001f9e0 {m.group(1)} jobs in memory (skipping duplicates)"
        if "Recommended" in msg and "skipped" in msg:
            return "  \U0001f4cb Recommended \u2014 unavailable"
        m = re.search(r"Recommended .+ (\d+) jobs", msg)
        if m:
            return f"  \U0001f4cb Recommended \u2014 {m.group(1)} jobs"
        if re.match(r"^Scanning \d+ custom", msg):
            return "\U0001f517 Checking custom search URLs..."
        if "Custom URL" in msg:
            m = re.search(r"(\d+)", msg)
            return f"  \U0001f517 Custom URL \u2014 {m.group(1)} jobs" if m and m.group(1) != "0" else "  \U0001f517 Custom URL \u2014 no new jobs"

        # Evaluation
        m = re.match(r"^Scanning (\d+)/(\d+): (.+?) @ (.+)", msg)
        if m:
            return f"\U0001f3af [{m.group(1)}/{m.group(2)}] {m.group(3)} @ {m.group(4)}"
        if "Already applied" in msg:
            return "  \u21b3 Already applied \u2014 skipping"
        if "Match score:" in msg:
            m = re.search(r"(\d+)%", msg)
            return f"  \u21b3 Match: {m.group(1)}%" if m else ""
        if "No score (LinkedIn Premium" in msg:
            return "  \u21b3 Using keyword matching (no Premium)"
        if "Fallback score:" in msg:
            m = re.search(r"(\d+)%", msg)
            return f"  \u21b3 Match: {m.group(1)}% (keyword)" if m else ""
        if "Not worth applying" in msg:
            m = re.search(r"(\d+)% < (\d+)%", msg)
            if m:
                return f"  \u21b3 \u274c Skipped \u2014 {m.group(1)}% below {m.group(2)}% threshold"
            return "  \u21b3 \u274c Below threshold"
        if "Worth applying" in msg and "DRY RUN" in msg:
            return "  \u21b3 \u2705 Qualifies! (dry run \u2014 not submitting)"
        if "Worth applying" in msg and "submitting" in msg:
            return "  \u21b3 \u2705 Submitting application..."
        if "Applied successfully" in msg:
            return "  \u21b3 \U0001f389 Applied!"
        if "External apply" in msg:
            return "  \u21b3 \U0001f517 External link saved"
        if "Paused" in msg and "human input" in msg:
            return "  \u21b3 \u23f8\ufe0f Needs your input"

        # Summary section
        if msg.startswith("\u2500") or msg == "SUMMARY:":
            return ""
        m = re.match(r"^Total jobs found:\s+(\d+)", msg)
        if m:
            return f"\n\U0001f4ca Run complete \u2014 {m.group(1)} jobs found"
        m = re.match(r"^Applied/would apply:\s+(\d+)", msg)
        if m:
            return f"  \u2705 Qualified: {m.group(1)}" if m.group(1) != "0" else ""
        m = re.match(r"^Skipped \(low score\):\s+(\d+)", msg)
        if m:
            return f"  \u23ed\ufe0f Skipped: {m.group(1)}" if m.group(1) != "0" else ""
        m = re.match(r"^External \(manual\):\s+(\d+)", msg)
        if m:
            return f"  \U0001f517 External: {m.group(1)}" if m.group(1) != "0" else ""
            return f"  \U0001f517 External: {m.group(1)}" if m.group(1) != "0" else ""

        # End
        if "Scan cycle complete" in msg:
            return "\u2705 Done!"
        if "Shutting down" in msg:
            return "\U0001f44b Shutting down"
        if "Checking application response" in msg:
            return "\U0001f4cb Checking for responses..."
        if "Could not check" in msg:
            return ""
        if "Session invalid" in msg:
            return "\u26a0\ufe0f Session expired \u2014 please log in to LinkedIn manually"
        if "Daily application cap" in msg:
            return "\U0001f6d1 Daily limit reached"

        # Default: pass through if short, skip if looks internal
        if re.match(r'^\w+\.py:\d+', msg) or len(msg) > 200:
            return ""
        return msg

    def _summarize_traceback(self, lines):
        """One-line user summary from a traceback."""
        import re
        text = "\n".join(lines)
        m = re.search(r'(TimeoutError|Error|Exception)[:\s]+(.+?)(?:\n|$)', text)
        if m:
            err = m.group(2).strip()[:100]
            if "Timeout" in m.group(1):
                if "search" in text:
                    return "\u26a0\ufe0f Search page timed out \u2014 retrying..."
                return "\u26a0\ufe0f Page timed out"
            if "context was destroyed" in err.lower() or "Protocol error" in err:
                return ""
            if "net::ERR" in err:
                return "\u26a0\ufe0f Network error"
            return f"\u26a0\ufe0f {err[:80]}"
        return ""

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
                run.output_log = "\n".join(self._output_lines)  # Store full output
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

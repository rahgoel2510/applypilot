"""Service routes — manage agent daemon lifecycle (start/stop/status)."""

import json
import os
import signal
import subprocess
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import AppSetting

router = APIRouter(prefix="/api/service")

SERVICE_KEY = "service_config"
PID_FILE = Path(__file__).parent / "agent_daemon.pid"
START_TIME_FILE = Path(__file__).parent / "agent_daemon_start"


class AutoStartRequest(BaseModel):
    enabled: bool


def _get_service_config(db: Session) -> dict:
    """Load service config from DB."""
    row = db.query(AppSetting).filter(AppSetting.key == SERVICE_KEY).first()
    if row and row.value:
        try:
            return json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            pass
    return {"auto_start": False}


def _save_service_config(db: Session, config: dict) -> None:
    """Persist service config to DB."""
    row = db.query(AppSetting).filter(AppSetting.key == SERVICE_KEY).first()
    value = json.dumps(config)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=SERVICE_KEY, value=value))
    db.commit()


def _is_running() -> tuple[bool, int | None]:
    """Check if the daemon is running by PID file."""
    if not PID_FILE.exists():
        return False, None
    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process actually exists
        os.kill(pid, 0)
        return True, pid
    except (ValueError, OSError, ProcessLookupError):
        # Stale PID file
        PID_FILE.unlink(missing_ok=True)
        START_TIME_FILE.unlink(missing_ok=True)
        return False, None


def _get_uptime() -> int:
    """Get uptime in seconds from start time file."""
    if not START_TIME_FILE.exists():
        return 0
    try:
        start_ts = float(START_TIME_FILE.read_text().strip())
        return int(time.time() - start_ts)
    except (ValueError, OSError):
        return 0


@router.get("/status")
def get_service_status(db: Session = Depends(get_db)):
    """Return current daemon status."""
    running, pid = _is_running()
    config = _get_service_config(db)
    return {
        "running": running,
        "pid": pid,
        "uptime_seconds": _get_uptime() if running else 0,
        "auto_start": config.get("auto_start", False),
    }


@router.post("/start")
def start_service(db: Session = Depends(get_db)):
    """Start the agent in daemon mode as a background process."""
    running, pid = _is_running()
    if running:
        return {"message": "Service already running", "pid": pid}

    try:
        # Launch the agent as a background subprocess
        agent_script = Path(__file__).parent.parent.parent / "main.py"

        # Determine the correct command
        if agent_script.exists():
            cmd = ["python", str(agent_script), "--daemon"]
        else:
            # Fallback: use module mode
            cmd = ["python", "-m", "applypilot", "serve", "--daemon"]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Save PID and start time
        PID_FILE.write_text(str(proc.pid))
        START_TIME_FILE.write_text(str(time.time()))

        return {"message": "Service started", "pid": proc.pid}

    except Exception as e:
        return {"message": f"Failed to start service: {str(e)}", "pid": None}


@router.post("/stop")
def stop_service():
    """Stop the agent daemon."""
    running, pid = _is_running()
    if not running:
        return {"message": "Service is not running"}

    try:
        os.kill(pid, signal.SIGTERM)
        # Wait briefly for process to terminate
        time.sleep(0.5)
        # Clean up PID files
        PID_FILE.unlink(missing_ok=True)
        START_TIME_FILE.unlink(missing_ok=True)
        return {"message": "Service stopped", "pid": pid}
    except OSError as e:
        PID_FILE.unlink(missing_ok=True)
        START_TIME_FILE.unlink(missing_ok=True)
        return {"message": f"Error stopping service: {str(e)}"}


@router.put("/auto-start")
def set_auto_start(req: AutoStartRequest, db: Session = Depends(get_db)):
    """Toggle auto-start on boot."""
    config = _get_service_config(db)
    config["auto_start"] = req.enabled
    _save_service_config(db, config)
    return {"message": f"Auto-start {'enabled' if req.enabled else 'disabled'}", "auto_start": req.enabled}

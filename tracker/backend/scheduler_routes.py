"""Scheduler routes — manage agent run scheduling configuration."""

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import AppSetting

router = APIRouter(prefix="/api/scheduler")

SCHEDULER_KEY = "scheduler_config"

DEFAULT_CONFIG = {
    "enabled": True,
    "interval_minutes": 60,
    "active_hours_start": "09:00",
    "active_hours_end": "18:00",
    "cron_expression": "",
    "days_of_week": ["Mon", "Tue", "Wed", "Thu", "Fri"],
}

DAY_MAP = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


class SchedulerConfig(BaseModel):
    enabled: bool = True
    interval_minutes: int = 60
    active_hours_start: str = "09:00"
    active_hours_end: str = "18:00"
    cron_expression: Optional[str] = ""
    days_of_week: list[str] = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def _get_config(db: Session) -> dict:
    """Load scheduler config from DB or return defaults."""
    row = db.query(AppSetting).filter(AppSetting.key == SCHEDULER_KEY).first()
    if row and row.value:
        try:
            return json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            pass
    return DEFAULT_CONFIG.copy()


def _save_config(db: Session, config: dict) -> None:
    """Persist scheduler config to DB."""
    row = db.query(AppSetting).filter(AppSetting.key == SCHEDULER_KEY).first()
    value = json.dumps(config)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=SCHEDULER_KEY, value=value))
    db.commit()


@router.get("")
def get_schedule(db: Session = Depends(get_db)):
    """Return current schedule configuration."""
    return _get_config(db)


@router.put("")
def update_schedule(config: SchedulerConfig, db: Session = Depends(get_db)):
    """Save schedule configuration."""
    data = config.model_dump()
    _save_config(db, data)
    return {"message": "Schedule updated", "config": data}


@router.get("/next-runs")
def get_next_runs(db: Session = Depends(get_db)):
    """Compute and return the next 5 scheduled run times based on config."""
    config = _get_config(db)

    if not config.get("enabled"):
        return {"next_runs": [], "message": "Scheduler is disabled"}

    interval = config.get("interval_minutes", 60)
    start_hour, start_min = _parse_time(config.get("active_hours_start", "09:00"))
    end_hour, end_min = _parse_time(config.get("active_hours_end", "18:00"))
    active_days = set(DAY_MAP.get(d, -1) for d in config.get("days_of_week", []))

    now = datetime.now()
    runs = []
    candidate = now + timedelta(minutes=interval)

    # Scan up to 7 days ahead to find 5 valid runs
    max_iterations = 1000
    iterations = 0
    while len(runs) < 5 and iterations < max_iterations:
        iterations += 1

        if candidate.weekday() in active_days:
            candidate_minutes = candidate.hour * 60 + candidate.minute
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min

            if start_minutes <= candidate_minutes <= end_minutes:
                runs.append(candidate.strftime("%Y-%m-%d %H:%M"))
                candidate += timedelta(minutes=interval)
                continue

        # Jump to next valid time
        candidate += timedelta(minutes=interval)

    return {"next_runs": runs}


def _parse_time(time_str: str) -> tuple[int, int]:
    """Parse HH:MM string into (hour, minute)."""
    try:
        parts = time_str.split(":")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 9, 0

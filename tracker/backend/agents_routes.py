"""Agents routes — manage agent types and their configurations."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import AppSetting

router = APIRouter(prefix="/api/agents")

AGENTS_KEY = "agents_config"

# Default agent type definitions
DEFAULT_AGENTS = [
    {
        "id": "scanner",
        "name": "Job Scanner",
        "description": "Continuously monitors LinkedIn for new job postings matching your saved searches and keywords.",
        "enabled": True,
        "config": {
            "keywords": ["Software Engineer", "Backend Developer"],
            "locations": ["Remote"],
            "posted_within": "24h",
            "max_results": 50,
        },
    },
    {
        "id": "applicant",
        "name": "Auto Applicant",
        "description": "Fills and submits LinkedIn Easy Apply forms end-to-end, handling multi-step flows.",
        "enabled": True,
        "config": {
            "dry_run": True,
            "max_applications_per_day": 25,
            "min_match_score": 70,
        },
    },
    {
        "id": "inmail_drafter",
        "name": "InMail Drafter",
        "description": "Generates personalized cold outreach messages to hiring managers and recruiters.",
        "enabled": False,
        "config": {
            "tone": "professional",
            "max_length": 300,
            "auto_send": False,
        },
    },
    {
        "id": "telegram_notifier",
        "name": "Telegram Notifier",
        "description": "Sends real-time alerts for new matches, successful applications, and fields needing your input.",
        "enabled": True,
        "config": {
            "notify_on_match": True,
            "notify_on_apply": True,
            "notify_on_error": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        },
    },
]


class AgentConfigUpdate(BaseModel):
    config: dict


class AgentToggle(BaseModel):
    enabled: bool


def _get_agents(db: Session) -> list[dict]:
    """Load agents config from DB or return defaults."""
    row = db.query(AppSetting).filter(AppSetting.key == AGENTS_KEY).first()
    if row and row.value:
        try:
            return json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            pass
    return [a.copy() for a in DEFAULT_AGENTS]


def _save_agents(db: Session, agents: list[dict]) -> None:
    """Persist agents config to DB."""
    row = db.query(AppSetting).filter(AppSetting.key == AGENTS_KEY).first()
    value = json.dumps(agents)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=AGENTS_KEY, value=value))
    db.commit()


def _find_agent(agents: list[dict], agent_id: str) -> tuple[int, dict | None]:
    """Find an agent by ID. Returns (index, agent) or (-1, None)."""
    for idx, agent in enumerate(agents):
        if agent["id"] == agent_id:
            return idx, agent
    return -1, None


@router.get("")
def get_agents(db: Session = Depends(get_db)):
    """Return list of all agent types with their configs."""
    return _get_agents(db)


@router.put("/{agent_id}")
def update_agent_config(agent_id: str, req: AgentConfigUpdate, db: Session = Depends(get_db)):
    """Update configuration for a specific agent type."""
    agents = _get_agents(db)
    idx, agent = _find_agent(agents, agent_id)

    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    agents[idx]["config"] = req.config
    _save_agents(db, agents)

    return {"message": f"Config updated for '{agent_id}'", "agent": agents[idx]}


@router.patch("/{agent_id}/toggle")
def toggle_agent(agent_id: str, req: AgentToggle, db: Session = Depends(get_db)):
    """Enable or disable an agent type."""
    agents = _get_agents(db)
    idx, agent = _find_agent(agents, agent_id)

    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    agents[idx]["enabled"] = req.enabled
    _save_agents(db, agents)

    return {"message": f"Agent '{agent_id}' {'enabled' if req.enabled else 'disabled'}", "agent": agents[idx]}

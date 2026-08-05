"""Agents routes — manage agent types and their configurations."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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
    {
        "id": "naukri_freshener",
        "name": "Naukri Profile Freshener",
        "description": "Keeps Naukri profile fresh by toggling summary and re-uploading resume daily.",
        "enabled": False,
        "config": {
            "frequency": "daily",
            "update_time": "08:00",
            "toggle_summary": True,
            "reupload_resume": True,
        },
    },
]


class AgentConfigUpdate(BaseModel):
    config: dict


class AgentToggle(BaseModel):
    enabled: bool


class AgentScheduleUpdate(BaseModel):
    schedule_minutes: Optional[int] = None
    schedule_time: Optional[str] = None


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


def _get_orchestrator_safe():
    """Import and return the orchestrator instance, or None if unavailable."""
    try:
        from linkedin_agent.multi_agent_orchestrator import get_orchestrator

        return get_orchestrator()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Orchestrator endpoints (placed BEFORE parameterized routes to avoid conflicts)
# ---------------------------------------------------------------------------


@router.get("/orchestrator/status")
def get_orchestrator_status():
    """Get orchestrator status (running, agent count, etc)."""
    orchestrator = _get_orchestrator_safe()
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not available — module not initialized",
        )

    try:
        agent_statuses = orchestrator.get_all_statuses()
        return {
            "running": orchestrator._running,
            "agent_count": len(agent_statuses),
            "agents": agent_statuses,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Orchestrator error: {exc}")


@router.post("/orchestrator/start")
async def start_orchestrator():
    """Start the orchestrator scheduler loop."""
    orchestrator = _get_orchestrator_safe()
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not available — module not initialized",
        )

    try:
        if orchestrator._running:
            raise HTTPException(
                status_code=409, detail="Orchestrator is already running"
            )
        await orchestrator.start()
        return {"message": "Orchestrator started", "running": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to start orchestrator: {exc}"
        )


@router.post("/orchestrator/stop")
async def stop_orchestrator():
    """Stop the orchestrator and all running agents."""
    orchestrator = _get_orchestrator_safe()
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not available — module not initialized",
        )

    try:
        if not orchestrator._running:
            raise HTTPException(
                status_code=409, detail="Orchestrator is not running"
            )
        await orchestrator.stop()
        return {"message": "Orchestrator stopped", "running": False}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to stop orchestrator: {exc}"
        )


# ---------------------------------------------------------------------------
# Existing CRUD endpoints
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Multi-agent orchestrator endpoints (parameterized)
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/trigger")
async def trigger_agent(agent_id: str):
    """Manually trigger an agent run (ignoring its schedule)."""
    orchestrator = _get_orchestrator_safe()
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not available — module not initialized",
        )

    try:
        result = await orchestrator.trigger_agent(agent_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not registered in orchestrator",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Trigger failed: {exc}")

    if not result.get("ok"):
        error_msg = result.get("error", "Unknown error")
        # Determine appropriate status code
        if "already running" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg)
        elif "disabled" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)

    return result


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: str):
    """Stop a running agent."""
    orchestrator = _get_orchestrator_safe()
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not available — module not initialized",
        )

    try:
        result = await orchestrator.stop_agent(agent_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not registered in orchestrator",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stop failed: {exc}")

    if not result.get("ok"):
        error_msg = result.get("error", "Unknown error")
        if "not running" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)

    return result


@router.get("/{agent_id}/status")
def get_agent_status(agent_id: str):
    """Get detailed status of a specific agent (state, last_run, next_run, consecutive_failures)."""
    orchestrator = _get_orchestrator_safe()
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not available — module not initialized",
        )

    try:
        return orchestrator.get_agent_status(agent_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not registered in orchestrator",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Status query failed: {exc}")


@router.get("/{agent_id}/history")
def get_agent_history(agent_id: str):
    """Get run history for an agent (most recent first)."""
    orchestrator = _get_orchestrator_safe()
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not available — module not initialized",
        )

    try:
        return orchestrator.get_agent_history(agent_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not registered in orchestrator",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"History query failed: {exc}")


@router.get("/{agent_id}/logs")
def get_agent_logs(agent_id: str, limit: int = Query(default=50, ge=1, le=500)):
    """Get recent logs for an agent."""
    orchestrator = _get_orchestrator_safe()
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not available — module not initialized",
        )

    try:
        logs = orchestrator.get_agent_logs(agent_id, limit=limit)
        return {"agent_id": agent_id, "logs": logs, "count": len(logs)}
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not registered in orchestrator",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Logs query failed: {exc}")


@router.put("/{agent_id}/schedule")
def update_agent_schedule(agent_id: str, req: AgentScheduleUpdate):
    """Update an agent's schedule (interval and/or preferred run time)."""
    orchestrator = _get_orchestrator_safe()
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not available — module not initialized",
        )

    try:
        orchestrator.update_schedule(
            agent_id,
            schedule_minutes=req.schedule_minutes,
            schedule_time=req.schedule_time,
        )
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not registered in orchestrator",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Schedule update failed: {exc}")

    # Return updated status
    status = orchestrator.get_agent_status(agent_id)
    return {"message": f"Schedule updated for '{agent_id}'", "agent": status}

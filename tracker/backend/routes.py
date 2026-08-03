"""API routes for Job Application Tracker."""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import (
    EVENT_STAGE_MAP,
    ActivityLog,
    FeedbackSignal,
    FeedbackSignalResponse,
    FeedbackSummaryResponse,
    InMailDraft,
    InMailDraftCreate,
    InMailDraftResponse,
    InMailDraftStatus,
    InMailDraftStatusUpdate,
    Job,
    JobCreate,
    JobResponse,
    JobSource,
    JobStage,
    JobUpdate,
    LogCreate,
    LogEventType,
    LogResponse,
    LogSeverity,
    LogsPageResponse,
    StageUpdate,
    StatsResponse,
    WebhookPayload,
)
from websocket_routes import push_event as ws_push_event, push_stats_update

router = APIRouter(prefix="/api")


# ===========================================================================
# Jobs CRUD
# ===========================================================================


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(
    stage: Optional[JobStage] = Query(None, description="Filter by stage"),
    company: Optional[str] = Query(None, description="Filter by company"),
    search: Optional[str] = Query(None, description="Search in title and company"),
    sort: Optional[str] = Query("newest", description="Sort order: newest or oldest"),
    db: Session = Depends(get_db),
):
    """List all jobs with optional filtering and sorting."""
    query = db.query(Job)

    if stage:
        query = query.filter(Job.stage == stage)

    if company:
        query = query.filter(Job.company.ilike(f"%{company}%"))

    if search:
        query = query.filter(
            (Job.title.ilike(f"%{search}%")) | (Job.company.ilike(f"%{search}%"))
        )

    if sort == "oldest":
        query = query.order_by(Job.date_added.asc())
    else:
        query = query.order_by(Job.date_added.desc())

    return query.all()


@router.get("/jobs/audit")
def audit_jobs(
    db: Session = Depends(get_db),
):
    """Return all jobs with their scores for audit, sorted by score descending.

    Useful for manual review of scoring accuracy. Returns id, title, company,
    match_score, stage, posting_url, and date_added.
    """
    jobs = (
        db.query(
            Job.id,
            Job.title,
            Job.company,
            Job.match_score,
            Job.stage,
            Job.posting_url,
            Job.date_added,
        )
        .order_by(Job.match_score.desc().nulls_last())
        .all()
    )

    return [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "match_score": j.match_score,
            "stage": j.stage.value if hasattr(j.stage, "value") else j.stage,
            "posting_url": j.posting_url,
            "date_added": j.date_added.isoformat() if j.date_added else None,
        }
        for j in jobs
    ]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get a single job by ID."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs", response_model=JobResponse, status_code=201)
def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    """Create a new job entry."""
    job = Job(
        id=str(uuid.uuid4()),
        **job_data.model_dump(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.put("/jobs/{job_id}", response_model=JobResponse)
def update_job(job_id: str, job_data: JobUpdate, db: Session = Depends(get_db)):
    """Update an existing job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    update_data = job_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)
    return job


@router.patch("/jobs/{job_id}/stage", response_model=JobResponse)
def update_job_stage(job_id: str, stage_data: StageUpdate, db: Session = Depends(get_db)):
    """Move a job to a new stage."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    old_stage = job.stage
    job.stage = stage_data.stage
    db.commit()
    db.refresh(job)

    # Log stage change
    _create_log(
        db,
        event_type=LogEventType.info,
        severity=LogSeverity.info,
        title=job.title,
        company=job.company,
        stage=stage_data.stage.value,
        message=f"Moved from {old_stage.value if hasattr(old_stage, 'value') else old_stage} → {stage_data.stage.value}",
    )

    # --- Self-learning: record feedback signal ---
    user_action = _map_stage_transition_to_action(old_stage, stage_data.stage)
    if user_action:
        feedback = FeedbackSignal(
            id=str(uuid.uuid4()),
            job_id=job.id,
            job_title=job.title,
            company=job.company,
            original_score=job.match_score,
            user_action=user_action,
        )
        db.add(feedback)
        db.commit()

    return job


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Delete a job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    db.delete(job)
    db.commit()
    return None


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Return counts per stage."""
    counts = (
        db.query(Job.stage, func.count(Job.id))
        .group_by(Job.stage)
        .all()
    )

    stats = {stage.value: 0 for stage in JobStage}
    for stage, count in counts:
        stats[stage.value if hasattr(stage, "value") else stage] = count

    total = sum(stats.values())
    return StatsResponse(**stats, total=total)


# ===========================================================================
# Agent Webhook (auto-creates log entries)
# ===========================================================================


@router.post("/webhook/agent", response_model=JobResponse, status_code=201)
def webhook_agent(payload: WebhookPayload, db: Session = Depends(get_db)):
    """Webhook for LinkedIn agent to push events.

    - 'discovered': creates a new job in discovered stage
    - 'submitted': updates discovered→applied (or creates if not found)
    - 'paused'/'skipped': updates discovered→saved (or creates if not found)
    Prevents duplicate jobs by matching on title + company.
    """
    stage = EVENT_STAGE_MAP[payload.event]

    # Check if this job already exists in tracker (prevent duplicates)
    existing = db.query(Job).filter(
        Job.title == payload.title,
        Job.company == payload.company,
    ).first()

    if existing:
        # Update existing job's stage (discovered → applied, etc.)
        if stage.value in ("applied",) or (
            existing.stage in (JobStage.discovered, JobStage.saved) and stage != JobStage.saved
        ):
            existing.stage = stage
        if payload.match_score is not None:
            existing.match_score = payload.match_score
        if payload.posting_url:
            existing.posting_url = payload.posting_url
        if payload.location:
            existing.location = payload.location
        db.commit()
        db.refresh(existing)
        job = existing
    else:
        # Create new job
        job = Job(
            id=str(uuid.uuid4()),
            title=payload.title,
            company=payload.company,
            location=payload.location,
            stage=stage,
            posting_url=payload.posting_url,
            match_score=payload.match_score,
            source=JobSource.agent,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    # Map agent event to log event type and severity
    event_log_map = {
        "discovered": (LogEventType.info, LogSeverity.info),
        "reached_out": (LogEventType.inmail_drafted, LogSeverity.success),
        "submitted": (LogEventType.job_submitted, LogSeverity.success),
        "paused": (LogEventType.job_paused, LogSeverity.warning),
        "skipped": (LogEventType.job_skipped, LogSeverity.info),
    }
    log_event, log_severity = event_log_map.get(
        payload.event.value, (LogEventType.info, LogSeverity.info)
    )

    # Build descriptive message
    score_str = f" (match: {payload.match_score:.0%})" if payload.match_score else ""
    messages = {
        "discovered": f"Job discovered — meets threshold{score_str}",
        "submitted": f"Application submitted{score_str}",
        "paused": f"Saved as draft — needs human input{score_str}",
        "skipped": f"Skipped — below threshold or external{score_str}",
    }
    message = messages.get(payload.event.value, f"Event: {payload.event.value}")

    # Create activity log entry
    log_entry = ActivityLog(
        id=str(uuid.uuid4()),
        event_type=log_event,
        severity=log_severity,
        title=payload.title,
        company=payload.company,
        stage=stage.value,
        message=message,
        metadata_json=json.dumps({
            "match_score": payload.match_score,
            "posting_url": payload.posting_url,
            "location": payload.location,
            "source": "agent_webhook",
        }),
    )
    db.add(log_entry)

    db.commit()
    db.refresh(job)

    # Push real-time WebSocket update
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(ws_push_event(
            event_type=payload.event.value,
            title=payload.title or "",
            company=payload.company or "",
            location=payload.location or "",
            match_score=payload.match_score,
            stage=payload.event.value,
            status="completed",
        ))
    except Exception:
        pass  # WebSocket errors should never break the API

    return job


# ===========================================================================
# Activity Logs API
# ===========================================================================


@router.get("/logs", response_model=LogsPageResponse)
def list_logs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    event_type: Optional[LogEventType] = Query(None, description="Filter by event type"),
    severity: Optional[LogSeverity] = Query(None, description="Filter by severity"),
    search: Optional[str] = Query(None, description="Search in message, title, company"),
    db: Session = Depends(get_db),
):
    """List activity logs with pagination and filtering."""
    query = db.query(ActivityLog)

    if event_type:
        query = query.filter(ActivityLog.event_type == event_type)

    if severity:
        query = query.filter(ActivityLog.severity == severity)

    if search:
        query = query.filter(
            (ActivityLog.message.ilike(f"%{search}%"))
            | (ActivityLog.title.ilike(f"%{search}%"))
            | (ActivityLog.company.ilike(f"%{search}%"))
        )

    total = query.count()
    logs = (
        query.order_by(ActivityLog.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return LogsPageResponse(
        logs=logs,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.post("/logs", response_model=LogResponse, status_code=201)
def create_log(log_data: LogCreate, db: Session = Depends(get_db)):
    """Create an activity log entry (agent pushes lifecycle events)."""
    log_entry = ActivityLog(
        id=str(uuid.uuid4()),
        event_type=log_data.event_type,
        severity=log_data.severity,
        title=log_data.title,
        company=log_data.company,
        stage=log_data.stage,
        message=log_data.message,
        metadata_json=log_data.metadata_json,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    # Push real-time WebSocket update for live dashboard
    try:
        import asyncio as _asyncio
        loop = _asyncio.get_event_loop()
        loop.create_task(ws_push_event(
            event_type=log_data.event_type or "info",
            title=log_data.title or "",
            company=log_data.company or "",
            stage=log_data.stage or "",
            status=log_data.severity or "info",
            message=log_data.message or "",
        ))
    except Exception:
        pass  # WebSocket errors should never break the API

    return log_entry


# ===========================================================================
# InMail Drafts API
# ===========================================================================


@router.post("/inmail-drafts", response_model=InMailDraftResponse, status_code=201)
def create_inmail_draft(draft_data: InMailDraftCreate, db: Session = Depends(get_db)):
    """Create a new InMail draft (called by the agent after drafting)."""
    draft = InMailDraft(
        id=str(uuid.uuid4()),
        job_id=draft_data.job_id,
        job_title=draft_data.job_title,
        company=draft_data.company,
        recruiter_name=draft_data.recruiter_name,
        draft_text=draft_data.draft_text,
        status=draft_data.status,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.get("/inmail-drafts", response_model=list[InMailDraftResponse])
def list_inmail_drafts(
    job_id: Optional[str] = Query(None, description="Filter by job_id"),
    status: Optional[InMailDraftStatus] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """List all InMail drafts, optionally filtered by job_id or status."""
    query = db.query(InMailDraft)

    if job_id:
        query = query.filter(InMailDraft.job_id == job_id)

    if status:
        query = query.filter(InMailDraft.status == status)

    return query.order_by(InMailDraft.created_at.desc()).all()


@router.get("/jobs/{job_id}/inmail", response_model=list[InMailDraftResponse])
def get_inmail_drafts_for_job(job_id: str, db: Session = Depends(get_db)):
    """Get all InMail drafts associated with a specific job."""
    drafts = (
        db.query(InMailDraft)
        .filter(InMailDraft.job_id == job_id)
        .order_by(InMailDraft.created_at.desc())
        .all()
    )
    return drafts


@router.patch("/inmail-drafts/{draft_id}", response_model=InMailDraftResponse)
def update_inmail_draft_status(
    draft_id: str,
    status_data: InMailDraftStatusUpdate,
    db: Session = Depends(get_db),
):
    """Update an InMail draft's status (e.g., mark as sent or skipped)."""
    draft = db.query(InMailDraft).filter(InMailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="InMail draft not found")

    draft.status = status_data.status
    db.commit()
    db.refresh(draft)
    return draft


# ===========================================================================
# Helpers
# ===========================================================================


def _map_stage_transition_to_action(old_stage: JobStage, new_stage: JobStage) -> str | None:
    """Map a stage transition to a feedback user_action string.

    Returns None if the transition doesn't map to a meaningful signal.
    """
    old_val = old_stage.value if hasattr(old_stage, "value") else old_stage
    new_val = new_stage.value if hasattr(new_stage, "value") else new_stage

    # any → interviewing = strong positive
    if new_val == "interviewing":
        return "promoted_to_interview"
    # any → offered = strongest positive
    if new_val == "offered":
        return "promoted_to_offer"
    # any → rejected = negative
    if new_val == "rejected":
        return "rejected"
    # discovered/saved → applied = manual apply (user liked it)
    if old_val in ("discovered", "saved") and new_val == "applied":
        return "manual_apply"

    return None


def _create_log(
    db: Session,
    event_type: LogEventType,
    severity: LogSeverity,
    message: str,
    title: Optional[str] = None,
    company: Optional[str] = None,
    stage: Optional[str] = None,
    metadata_json: Optional[str] = None,
) -> None:
    """Internal helper to create a log entry."""
    log_entry = ActivityLog(
        id=str(uuid.uuid4()),
        event_type=event_type,
        severity=severity,
        title=title,
        company=company,
        stage=stage,
        message=message,
        metadata_json=metadata_json,
    )
    db.add(log_entry)
    db.commit()


# ===========================================================================
# Feedback / Self-Learning API
# ===========================================================================


@router.get("/feedback/summary", response_model=FeedbackSummaryResponse)
def get_feedback_summary(db: Session = Depends(get_db)):
    """Return aggregated feedback signals for self-learning.

    Provides:
    - Total signals by action type
    - Average original_score per action (scoring calibration)
    - Companies the user consistently promotes (positive signal)
    - Companies the user consistently rejects (negative signal)
    """
    # Total signals by action type
    action_counts = (
        db.query(FeedbackSignal.user_action, func.count(FeedbackSignal.id))
        .group_by(FeedbackSignal.user_action)
        .all()
    )
    total_signals = {action: count for action, count in action_counts}

    # Average original_score by action
    score_avgs = (
        db.query(FeedbackSignal.user_action, func.avg(FeedbackSignal.original_score))
        .group_by(FeedbackSignal.user_action)
        .all()
    )
    avg_score_by_action = {
        action: round(avg, 4) if avg is not None else None
        for action, avg in score_avgs
    }

    # Companies consistently promoted (interview + offer, appearing 2+ times)
    positive_actions = ("promoted_to_interview", "promoted_to_offer", "manual_apply")
    promoted_q = (
        db.query(FeedbackSignal.company, func.count(FeedbackSignal.id).label("cnt"))
        .filter(FeedbackSignal.user_action.in_(positive_actions))
        .group_by(FeedbackSignal.company)
        .having(func.count(FeedbackSignal.id) >= 2)
        .all()
    )
    promoted_companies = [company for company, _ in promoted_q]

    # Companies consistently rejected (appearing 2+ times)
    rejected_q = (
        db.query(FeedbackSignal.company, func.count(FeedbackSignal.id).label("cnt"))
        .filter(FeedbackSignal.user_action == "rejected")
        .group_by(FeedbackSignal.company)
        .having(func.count(FeedbackSignal.id) >= 2)
        .all()
    )
    rejected_companies = [company for company, _ in rejected_q]

    return FeedbackSummaryResponse(
        total_signals=total_signals,
        avg_score_by_action=avg_score_by_action,
        promoted_companies=promoted_companies,
        rejected_companies=rejected_companies,
    )


# ===========================================================================
# Agent Control API
# ===========================================================================

from pydantic import BaseModel as PydanticBaseModel
from agent_control import get_controller, AgentState


class AgentTriggerRequest(PydanticBaseModel):
    mode: str = "single"  # "single" or "daemon"
    dry_run: bool = True  # Default to dry-run for safety
    limit: int | None = None
    match_threshold: float | None = None
    collection: str = "Recommended"
    search_mode: str | None = None  # "aggressive", "active", "passive"


@router.post("/agent/trigger")
def trigger_agent(req: AgentTriggerRequest, db: Session = Depends(get_db)):
    """Trigger the LinkedIn agent to start scanning."""
    controller = get_controller()
    result = controller.trigger(
        mode=req.mode,
        dry_run=req.dry_run,
        limit=req.limit,
        match_threshold=req.match_threshold,
        collection=req.collection,
        search_mode=req.search_mode,
    )

    # Log the trigger event
    mode_str = "daemon" if req.mode == "daemon" else "single cycle"
    dry_str = " (DRY RUN)" if req.dry_run else ""
    limit_str = f", limit: {req.limit}" if req.limit else ""
    _create_log(
        db,
        event_type=LogEventType.agent_start,
        severity=LogSeverity.success if "error" not in result else LogSeverity.error,
        message=f"Agent triggered — {mode_str}{dry_str}{limit_str}",
        metadata_json=json.dumps(req.model_dump()),
    )

    return result


@router.post("/agent/stop")
def stop_agent(db: Session = Depends(get_db)):
    """Stop the running agent."""
    controller = get_controller()
    result = controller.stop()

    _create_log(
        db,
        event_type=LogEventType.agent_stop,
        severity=LogSeverity.info,
        message="Agent stopped via control panel",
    )

    return result


@router.get("/agent/status")
def get_agent_status():
    """Get current agent status."""
    controller = get_controller()
    return controller.status.to_dict()


@router.get("/agent/session")
def check_linkedin_session():
    """Quick check if LinkedIn session exists (checks file presence, not validity)."""
    import os
    from pathlib import Path

    # Check common session paths
    paths_to_check = [
        Path.home() / ".local" / "share" / "linkedin_agent" / "browser_data" / "Default",
        Path("/root/.local/share/linkedin_agent/browser_data/Default"),  # Docker
        Path.home() / "Library" / "Application Support" / "linkedin_agent" / "browser_data" / "Default",  # macOS
    ]

    for p in paths_to_check:
        if p.exists():
            # Check if there are cookie files
            cookies = p / "Cookies"
            local_storage = p / "Local Storage"
            has_cookies = cookies.exists() or local_storage.exists()
            return {
                "session_exists": True,
                "has_cookies": has_cookies,
                "path": str(p.parent),
                "message": "Session files found. Agent should connect without login." if has_cookies else "Session directory exists but no cookies found.",
            }

    return {
        "session_exists": False,
        "has_cookies": False,
        "path": None,
        "message": "No LinkedIn session found. Copy your browser session or run test_browser_dry_run.py first.",
    }


@router.get("/agent/screenshot")
def get_agent_screenshot():
    """Get the latest pipeline screenshot as base64."""
    import base64
    from pathlib import Path

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots"
    if not screenshot_dir.exists():
        # Try the standard location
        from platformdirs import user_data_dir
        screenshot_dir = Path(user_data_dir("linkedin_agent", "linkedin_agent")) / "screenshots"

    if not screenshot_dir.exists():
        return {"image": None, "timestamp": None, "filename": None}

    # Get the most recent .png
    screenshots = sorted(screenshot_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not screenshots:
        return {"image": None, "timestamp": None, "filename": None}

    latest = screenshots[0]
    with open(latest, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    return {
        "image": f"data:image/png;base64,{b64}",
        "timestamp": latest.stat().st_mtime,
        "filename": latest.name,
    }


@router.post("/agent/screenshot")
async def upload_agent_screenshot(request: Request):
    """Receive a screenshot from the debug pipeline."""
    import base64
    from pathlib import Path

    data = await request.json()
    image_b64 = data.get("image", "")
    name = data.get("name", "pipeline_step")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    filepath = screenshot_dir / f"{name}.png"
    img_data = base64.b64decode(image_b64)
    filepath.write_bytes(img_data)

    # Push WebSocket event so frontend refreshes
    from websocket_routes import push_event
    await push_event("screenshot", message=name)

    return {"ok": True, "path": str(filepath)}


@router.get("/agent/output")
def get_agent_output(tail: int = 50):
    """Get recent agent stdout output (last N lines)."""
    controller = get_controller()
    lines = controller.output
    return {"lines": lines[-tail:], "total_lines": len(lines)}


@router.get("/agent/runs")
def list_agent_runs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """List agent run history, most recent first."""
    from models import AgentRun
    runs = db.query(AgentRun).order_by(AgentRun.started_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "status": r.status,
            "mode": r.mode,
            "dry_run": r.dry_run,
            "limit": r.limit,
            "collection": r.collection,
            "jobs_processed": r.jobs_processed,
            "jobs_applied": r.jobs_applied,
            "jobs_skipped": r.jobs_skipped,
            "duration_seconds": r.duration_seconds,
            "error_message": r.error_message,
        }
        for r in runs
    ]


@router.get("/agent/runs/{run_id}")
def get_agent_run(run_id: str, db: Session = Depends(get_db)):
    """Get a specific run's details including full log output."""
    from models import AgentRun
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    output_log = run.output_log or ""

    # If run is still active, grab live output from the controller buffer
    if run.status == "running" and not output_log:
        try:
            from agent_control import get_controller
            controller = get_controller()
            if controller._status.run_id == run_id:
                output_log = "\n".join(controller.output)
        except Exception:
            pass

    return {
        "id": run.id,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "status": run.status,
        "mode": run.mode,
        "dry_run": run.dry_run,
        "limit": run.limit,
        "match_threshold": run.match_threshold,
        "collection": run.collection,
        "jobs_processed": run.jobs_processed,
        "jobs_applied": run.jobs_applied,
        "jobs_skipped": run.jobs_skipped,
        "jobs_paused": run.jobs_paused,
        "jobs_errored": run.jobs_errored,
        "duration_seconds": run.duration_seconds,
        "error_message": run.error_message,
        "output_log": output_log,
    }


def _parse_pipeline_steps(output: str) -> list:
    """Parse agent output into GitHub Actions-style named steps with sub-steps, durations, and logs."""
    import re
    from datetime import datetime

    lines = [l for l in output.split("\n") if l.strip()]
    if not lines:
        return []

    def extract_time(line):
        m = re.search(r'\[?(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2}:\d{2})\]?', line)
        if m:
            try:
                return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%m/%d/%y %H:%M:%S")
            except Exception:
                pass
        return None

    def clean_line(line):
        line = re.sub(r'^\[?\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\]?\s*', '', line)
        line = re.sub(r'^(INFO|WARNING|ERROR|DEBUG|CRITICAL)\s+', '', line)
        line = re.sub(r'\s+\w+\.py:\d+\s*$', '', line)
        line = re.sub(r'\s{3,}', '  ', line).strip()
        return line

    # Parse ALL lines into timestamped entries
    entries = []
    for line in lines:
        ts = extract_time(line)
        cleaned = clean_line(line)
        if cleaned and len(cleaned) > 1:
            entries.append({"ts": ts, "raw": line, "text": cleaned})

    if not entries:
        return []

    # Define step boundaries
    step_defs = [
        {"id": "init", "icon": "🚀", "name": "Initialize Pipeline",
         "trigger": r"(Pipeline started|Starting job search|Running single scan|Search mode:|URGENT MODE)"},
        {"id": "browser", "icon": "🌐", "name": "Launch Browser",
         "trigger": r"(Launching browser|Browser launched|Browser ready)"},
        {"id": "session", "icon": "🔑", "name": "Verify LinkedIn Session",
         "trigger": r"(Checking.*session|LinkedIn connected|Already logged in|Session expired|Logging in|logged in)"},
        {"id": "discover", "icon": "🔍", "name": "Discover Jobs",
         "trigger": r"(LinkedIn scanning|Checking Recommended|Searching by keywords|Across locations)"},
        {"id": "search", "icon": "📡", "name": "Search & Collect",
         "trigger": r"(Combined search|Searched jobs|custom URL|Custom URL|individual search|OR search)"},
        {"id": "evaluate", "icon": "🎯", "name": "Evaluate & Score Jobs",
         "trigger": r"(Found \d+ unique|Scanning \d+/\d+|Dedup DB:)"},
        {"id": "decide", "icon": "📝", "name": "Score & Decide",
         "trigger": r"(Fallback score|Match score|Not worth|Worth applying|Applied|External apply|Paused)"},
        {"id": "summary", "icon": "📊", "name": "Generate Report",
         "trigger": r"(SUMMARY:|Total jobs found:|─{5,}|Tally report)"},
        {"id": "status_check", "icon": "📋", "name": "Check Responses",
         "trigger": r"(Checking application response|application statuses)"},
        {"id": "shutdown", "icon": "🏁", "name": "Shutdown & Cleanup",
         "trigger": r"(Scan cycle complete|Shutting down|Shutdown complete|Browser closed|Agent shutting)"},
    ]

    # Assign entries to steps
    steps = []
    current_step = None
    current_entries = []

    for entry in entries:
        matched_def = None
        for sdef in step_defs:
            if re.search(sdef["trigger"], entry["text"]):
                if current_step and current_step["id"] == sdef["id"]:
                    break  # Same step, don't re-trigger
                matched_def = sdef
                break

        if matched_def:
            # Finalize previous step
            if current_step and current_entries:
                steps.append(_finalize_step(current_step, current_entries))
            current_step = {"id": matched_def["id"], "icon": matched_def["icon"], "name": matched_def["name"]}
            current_entries = [entry]
        elif current_step:
            current_entries.append(entry)

    # Finalize last step
    if current_step and current_entries:
        steps.append(_finalize_step(current_step, current_entries))

    # Number steps
    for i, s in enumerate(steps):
        s["number"] = i + 1

    return steps


def _finalize_step(step_def, entries):
    """Build a step object with sub-steps, duration, status, and logs."""
    import re

    # Duration from first to last timestamp
    times = [e["ts"] for e in entries if e["ts"]]
    duration = None
    start_time = None
    end_time = None
    if len(times) >= 2:
        duration = int((times[-1] - times[0]).total_seconds())
        start_time = times[0].strftime("%H:%M:%S")
        end_time = times[-1].strftime("%H:%M:%S")
    elif len(times) == 1:
        start_time = times[0].strftime("%H:%M:%S")
        duration = 0

    # Build sub-steps: each log line becomes a sub-step with its own duration
    sub_steps = []
    for i, entry in enumerate(entries):
        text = entry["text"]
        if not text or len(text) < 2:
            continue

        # Calculate duration to next entry
        sub_dur = None
        if entry["ts"] and i + 1 < len(entries) and entries[i + 1]["ts"]:
            sub_dur = int((entries[i + 1]["ts"] - entry["ts"]).total_seconds())

        # Determine sub-step status
        sub_status = "success"
        if re.search(r'error|failed|exception', text, re.I):
            sub_status = "error"
        elif re.search(r'warn|expired|invalid|blocked|could not|abort', text, re.I):
            sub_status = "warning"

        sub_steps.append({
            "text": text,
            "duration_seconds": sub_dur,
            "timestamp": entry["ts"].strftime("%H:%M:%S") if entry["ts"] else None,
            "status": sub_status,
        })

    # Overall step status
    status = "success"
    for ss in sub_steps:
        if ss["status"] == "error":
            status = "error"
            break
        if ss["status"] == "warning":
            status = "warning"

    return {
        **step_def,
        "duration_seconds": duration,
        "start_time": start_time,
        "end_time": end_time,
        "status": status,
        "sub_steps": sub_steps,
        "log_count": len(sub_steps),
    }


@router.get("/agent/runs/{run_id}/analysis")
def get_run_analysis(run_id: str, db: Session = Depends(get_db)):
    """Parse run output_log into structured job events for the Analysis Mode view."""
    import re
    from models import AgentRun

    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    output = run.output_log or ""

    # If run is still active, grab live output from the controller buffer
    if run.status == "running" and not output:
        try:
            from agent_control import get_controller
            controller = get_controller()
            if controller._status.run_id == run_id:
                output = "\n".join(controller.output)
        except Exception:
            pass

    lines = output.split("\n")

    # --- Parse into GitHub Actions-style pipeline steps ---
    steps = _parse_pipeline_steps(output)

    # --- Parse pipeline phases ---
    phases = []
    phase_patterns = [
        (r"Pipeline started", "pipeline_start", "Pipeline Initialized"),
        (r"Launching browser", "browser_launch", "Launching Browser"),
        (r"Browser ready \(([0-9.]+)s\)", "browser_ready", "Browser Ready"),
        (r"LinkedIn connected", "linkedin_connected", "LinkedIn Connected"),
        (r"LinkedIn scanning started", "scanning_start", "Discovery Phase Started"),
        (r"Found (\d+) unique jobs", "discovery_complete", "Discovery Complete"),
        (r"Dedup DB: (\d+) jobs previously seen", "dedup_loaded", "Dedup Database Loaded"),
    ]

    for line in lines:
        for pattern, phase_id, label in phase_patterns:
            m = re.search(pattern, line)
            if m:
                detail = m.group(1) if m.lastindex else None
                phases.append({"id": phase_id, "label": label, "detail": detail})
                break

    # --- Parse individual job events ---
    jobs = []
    current_job = None

    for line in lines:
        # Detect "Scanning N/M: Title @ Company"
        scan_match = re.search(r"Scanning (\d+)/(\d+): (.+?) @ (.+)", line)
        if scan_match:
            if current_job:
                jobs.append(current_job)
            current_job = {
                "index": int(scan_match.group(1)),
                "total": int(scan_match.group(2)),
                "title": scan_match.group(3).strip(),
                "company": scan_match.group(4).strip(),
                "score": None,
                "score_method": None,
                "decision": None,
                "reason": None,
                "events": [],
            }
            continue

        if not current_job:
            continue

        # Score detection
        score_match = re.search(r"Match score: (\d+)/(\d+) = (\d+)%", line)
        if score_match:
            current_job["score"] = int(score_match.group(3)) / 100
            current_job["score_method"] = "premium"
            current_job["events"].append({"type": "score", "detail": f"{score_match.group(1)}/{score_match.group(2)} = {score_match.group(3)}%"})
            continue

        fallback_match = re.search(r"Fallback score: (\d+)% \(keyword match\)", line)
        if fallback_match:
            current_job["score"] = int(fallback_match.group(1)) / 100
            current_job["score_method"] = "fallback"
            current_job["events"].append({"type": "score", "detail": f"{fallback_match.group(1)}% (keyword match)"})
            continue

        # No score available
        if re.search(r"No score \(LinkedIn Premium needed\)", line):
            current_job["events"].append({"type": "no_score", "detail": "LinkedIn Premium needed"})
            continue

        # Decision outcomes
        if re.search(r"Worth applying.*DRY RUN", line):
            current_job["decision"] = "would_apply"
            current_job["reason"] = "Score meets threshold (dry run)"
            current_job["events"].append({"type": "decision", "detail": "Would apply (dry run)"})
            continue

        if re.search(r"Worth applying.*submitting", line):
            current_job["decision"] = "applying"
            current_job["events"].append({"type": "decision", "detail": "Submitting application"})
            continue

        if re.search(r"Applied successfully", line):
            current_job["decision"] = "applied"
            current_job["reason"] = "Application submitted"
            current_job["events"].append({"type": "applied", "detail": "Application submitted successfully"})
            continue

        if re.search(r"Not worth applying \((\d+)% < (\d+)%\)", line):
            m2 = re.search(r"Not worth applying \((\d+)% < (\d+)%\)", line)
            current_job["decision"] = "skipped"
            current_job["reason"] = f"Score {m2.group(1)}% below threshold {m2.group(2)}%"
            current_job["events"].append({"type": "decision", "detail": f"Skipped — {m2.group(1)}% < {m2.group(2)}%"})
            continue

        if re.search(r"Already applied", line):
            current_job["decision"] = "skipped"
            current_job["reason"] = "Already applied"
            current_job["events"].append({"type": "decision", "detail": "Already applied"})
            continue

        if re.search(r"External apply", line):
            ext_match = re.search(r"External apply: (.+)", line)
            current_job["decision"] = "external"
            current_job["reason"] = "External application link"
            url = ext_match.group(1).strip() if ext_match else None
            current_job["external_url"] = url
            current_job["events"].append({"type": "external", "detail": url or "External link"})
            continue

        if re.search(r"Paused.*human input", line):
            current_job["decision"] = "paused"
            current_job["reason"] = "Needs human input"
            current_job["events"].append({"type": "paused", "detail": "Awaiting human input"})
            continue

        if re.search(r"Error:", line):
            err_match = re.search(r"Error: (.+)", line)
            current_job["decision"] = "error"
            current_job["reason"] = err_match.group(1).strip() if err_match else "Unknown error"
            current_job["events"].append({"type": "error", "detail": current_job["reason"]})
            continue

    if current_job:
        jobs.append(current_job)

    # --- Generate summary insights ---
    total_jobs_found = 0
    found_match = re.search(r"Found (\d+) unique jobs", output)
    if found_match:
        total_jobs_found = int(found_match.group(1))

    dedup_count = 0
    dedup_match = re.search(r"Dedup DB: (\d+) jobs previously seen", output)
    if dedup_match:
        dedup_count = int(dedup_match.group(1))

    applied_jobs = [j for j in jobs if j["decision"] in ("applied", "would_apply")]
    skipped_jobs = [j for j in jobs if j["decision"] == "skipped"]
    external_jobs = [j for j in jobs if j["decision"] == "external"]
    paused_jobs = [j for j in jobs if j["decision"] == "paused"]
    error_jobs = [j for j in jobs if j["decision"] == "error"]

    scores = [j["score"] for j in jobs if j["score"] is not None]
    avg_score = sum(scores) / len(scores) if scores else None
    top_match = max(scores) if scores else None

    # Companies breakdown
    companies = {}
    for j in jobs:
        co = j.get("company", "Unknown")
        if co not in companies:
            companies[co] = {"applied": 0, "skipped": 0, "external": 0, "total": 0}
        companies[co]["total"] += 1
        if j["decision"] in ("applied", "would_apply"):
            companies[co]["applied"] += 1
        elif j["decision"] == "skipped":
            companies[co]["skipped"] += 1
        elif j["decision"] == "external":
            companies[co]["external"] += 1

    # Search sources
    sources = []
    for line in lines:
        rec_match = re.search(r"Recommended → (\d+) jobs", line)
        if rec_match:
            sources.append({"source": "Recommended", "count": int(rec_match.group(1))})
        combined_match = re.search(r"Combined search \((.+?)\) → (\d+) jobs", line)
        if combined_match:
            sources.append({"source": f"Search: {combined_match.group(1)}", "count": int(combined_match.group(2))})
        kw_match = re.search(r"'(.+?)' in (.+?) → (\d+) new jobs", line)
        if kw_match:
            sources.append({"source": f"{kw_match.group(1)} in {kw_match.group(2)}", "count": int(kw_match.group(3))})

    return {
        "run_id": run.id,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration_seconds": run.duration_seconds,
        "mode": run.mode,
        "dry_run": run.dry_run,
        "match_threshold": run.match_threshold,
        "collection": run.collection,
        "error_message": run.error_message,
        "summary": {
            "total_discovered": total_jobs_found,
            "dedup_database_size": dedup_count,
            "jobs_evaluated": len(jobs),
            "applied": len(applied_jobs),
            "skipped": len(skipped_jobs),
            "external": len(external_jobs),
            "paused": len(paused_jobs),
            "errors": len(error_jobs),
            "avg_score": round(avg_score * 100) if avg_score else None,
            "top_score": round(top_match * 100) if top_match else None,
        },
        "phases": phases,
        "steps": steps,
        "jobs": jobs,
        "companies": companies,
        "sources": sources,
        "output_log": run.output_log,
    }


@router.post("/agent/diagnose")
def diagnose_agent_failure(db: Session = Depends(get_db)):
    """Diagnose the last failed run using LLM auto-repair."""
    from models import AgentRun
    from auto_repair import diagnose_error, DiagnosisResult

    # Get the most recent failed or completed-with-error run
    run = db.query(AgentRun).filter(
        AgentRun.status.in_(["failed", "completed"])
    ).order_by(AgentRun.started_at.desc()).first()

    if not run:
        return {"diagnosed": False, "message": "No runs found to diagnose."}

    if not run.error_message and not run.output_log:
        return {"diagnosed": False, "message": "Last run has no error or output to analyze."}

    error_context = run.error_message or ""
    output_context = run.output_log or ""

    diagnosis = diagnose_error(error_context, output_context)

    return {
        "diagnosed": True,
        "run_id": run.id,
        "run_status": run.status,
        "diagnosis": diagnosis.model_dump(),
    }


@router.post("/agent/diagnose/{run_id}")
def diagnose_specific_run(run_id: str, db: Session = Depends(get_db)):
    """Diagnose a specific run using LLM auto-repair."""
    from models import AgentRun
    from auto_repair import diagnose_error

    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    error_context = run.error_message or ""
    output_context = run.output_log or ""

    if not error_context and not output_context:
        return {"diagnosed": False, "message": "No error or output to analyze."}

    diagnosis = diagnose_error(error_context, output_context)

    return {
        "diagnosed": True,
        "run_id": run.id,
        "diagnosis": diagnosis.model_dump(),
    }


@router.post("/agent/repair")
def auto_repair_and_retry(db: Session = Depends(get_db)):
    """Diagnose last failure, apply fix, and retry the agent."""
    from models import AgentRun
    from auto_repair import diagnose_error, build_retry_params

    controller = get_controller()

    if controller.status.state == AgentState.running:
        return {"message": "Agent is already running. Stop it first."}

    # Get last failed run
    run = db.query(AgentRun).filter(
        AgentRun.status == "failed"
    ).order_by(AgentRun.started_at.desc()).first()

    if not run:
        return {"diagnosed": False, "retried": False, "message": "No failed runs to repair."}

    # Diagnose
    diagnosis = diagnose_error(run.error_message or "", run.output_log or "")

    if not diagnosis.auto_fixable:
        return {
            "diagnosed": True,
            "diagnosis": diagnosis.model_dump(),
            "retried": False,
            "message": f"Not auto-fixable. {diagnosis.user_action_required}",
        }

    # Build retry params
    original_config = {
        "mode": run.mode or "single",
        "dry_run": run.dry_run == "True",
        "limit": int(run.limit) if run.limit else None,
    }
    retry_config = build_retry_params(diagnosis, original_config)

    # Retry with adjusted params
    result = controller.trigger(
        mode=retry_config.get("mode", "single"),
        dry_run=retry_config.get("dry_run", True),
        limit=retry_config.get("limit"),
    )

    return {
        "diagnosed": True,
        "diagnosis": diagnosis.model_dump(),
        "retried": True,
        "retry_config": retry_config,
        "agent_result": result,
        "message": f"Diagnosed: {diagnosis.diagnosis}. Retrying with adjusted parameters.",
    }

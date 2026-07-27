"""API routes for Job Application Tracker."""

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import (
    EVENT_STAGE_MAP,
    ActivityLog,
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
    return log_entry


# ===========================================================================
# Helpers
# ===========================================================================


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

"""Privacy/GDPR endpoints for ApplyPilot.

Provides:
- Right to Erasure (GDPR Art. 17): DELETE /api/privacy/delete-all
- Data Portability (GDPR Art. 20): GET /api/privacy/export
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Job, ActivityLog, AgentRun, FeedbackSignal, InMailDraft, Todo

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


def _serialize_row(row: Any) -> dict:
    """Convert a SQLAlchemy model instance to a JSON-safe dict."""
    result = {}
    for col in row.__table__.columns:
        value = getattr(row, col.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        result[col.name] = value
    return result


@router.get("/export")
def export_all_data(db: Session = Depends(get_db)):
    """Export all user data in JSON format (GDPR Art. 20 - Data Portability).
    
    Returns all tracked jobs, activity logs, agent runs, feedback signals,
    InMail drafts, and todos as structured JSON.
    """
    data = {
        "exported_at": datetime.now().isoformat(),
        "jobs": [_serialize_row(r) for r in db.query(Job).all()],
        "activity_logs": [_serialize_row(r) for r in db.query(ActivityLog).all()],
        "agent_runs": [_serialize_row(r) for r in db.query(AgentRun).all()],
        "feedback_signals": [_serialize_row(r) for r in db.query(FeedbackSignal).all()],
        "inmail_drafts": [_serialize_row(r) for r in db.query(InMailDraft).all()],
        "todos": [_serialize_row(r) for r in db.query(Todo).all()],
    }
    
    # Add record counts for summary
    data["summary"] = {
        table: len(records) for table, records in data.items()
        if isinstance(records, list)
    }
    
    return data


@router.delete("/delete-all")
def delete_all_data(db: Session = Depends(get_db)):
    """Delete all user data (GDPR Art. 17 - Right to Erasure).
    
    Removes all tracked jobs, activity logs, agent runs, feedback signals,
    InMail drafts, and todos. Does NOT delete application settings (config).
    
    This action is irreversible.
    """
    counts = {}
    
    # Delete in dependency order (children before parents if any FKs)
    tables = [
        ("inmail_drafts", InMailDraft),
        ("feedback_signals", FeedbackSignal),
        ("activity_logs", ActivityLog),
        ("agent_runs", AgentRun),
        ("todos", Todo),
        ("jobs", Job),
    ]
    
    for name, model in tables:
        count = db.query(model).delete()
        counts[name] = count
    
    db.commit()
    
    total = sum(counts.values())
    return {
        "message": f"All user data deleted ({total} records removed)",
        "deleted_counts": counts,
        "total_deleted": total,
        "note": "Application settings (config) were preserved. Use /api/settings to manage those.",
    }

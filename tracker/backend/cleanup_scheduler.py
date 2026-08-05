"""Data retention scheduler — automatic cleanup of old records.

Runs as a background task within the FastAPI app (using asyncio),
purging records older than configured retention periods.

Default retention:
- Activity logs: 90 days
- Agent runs: 30 days (keep last 100 regardless)
- Screenshots: 24 hours
- Audit log: 365 days
- Jobs: never (user data, only deleted via privacy endpoint)
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Retention periods (configurable via env)
RETENTION_ACTIVITY_LOGS_DAYS = int(os.environ.get('RETENTION_LOGS_DAYS', '90'))
RETENTION_AGENT_RUNS_DAYS = int(os.environ.get('RETENTION_RUNS_DAYS', '30'))
RETENTION_SCREENSHOTS_HOURS = int(os.environ.get('RETENTION_SCREENSHOTS_HOURS', '24'))
RETENTION_AUDIT_LOG_DAYS = int(os.environ.get('RETENTION_AUDIT_DAYS', '365'))
MIN_AGENT_RUNS_KEPT = 100  # Always keep at least this many runs

# Run cleanup every 6 hours
CLEANUP_INTERVAL_SECONDS = int(os.environ.get('CLEANUP_INTERVAL_SECONDS', '21600'))


def cleanup_activity_logs(db: Session) -> int:
    """Delete activity logs older than retention period."""
    from models import ActivityLog
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_ACTIVITY_LOGS_DAYS)
    count = db.query(ActivityLog).filter(ActivityLog.timestamp < cutoff).delete()
    db.commit()
    return count


def cleanup_agent_runs(db: Session) -> int:
    """Delete agent runs older than retention period, keeping at least MIN_AGENT_RUNS_KEPT."""
    from models import AgentRun
    total_runs = db.query(AgentRun).count()
    if total_runs <= MIN_AGENT_RUNS_KEPT:
        return 0

    cutoff = datetime.utcnow() - timedelta(days=RETENTION_AGENT_RUNS_DAYS)
    # Get IDs of the most recent runs to keep
    keep_ids = [
        r.id for r in db.query(AgentRun.id)
        .order_by(AgentRun.started_at.desc())
        .limit(MIN_AGENT_RUNS_KEPT)
        .all()
    ]
    count = db.query(AgentRun).filter(
        AgentRun.started_at < cutoff,
        ~AgentRun.id.in_(keep_ids)
    ).delete(synchronize_session=False)
    db.commit()
    return count


def cleanup_screenshots() -> int:
    """Delete screenshot files older than retention period."""
    screenshot_dir = Path(__file__).parent.parent.parent / 'screenshots'
    if not screenshot_dir.exists():
        return 0

    cutoff = time.time() - (RETENTION_SCREENSHOTS_HOURS * 3600)
    removed = 0
    for f in screenshot_dir.glob('*.png'):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def cleanup_audit_logs(db: Session) -> int:
    """Delete audit log entries older than retention period."""
    try:
        from audit_log import AuditEntry
        cutoff = datetime.utcnow() - timedelta(days=RETENTION_AUDIT_LOG_DAYS)
        count = db.query(AuditEntry).filter(AuditEntry.timestamp < cutoff).delete()
        db.commit()
        return count
    except Exception:
        return 0


def run_cleanup(db: Session) -> dict:
    """Run all cleanup tasks. Returns counts of deleted records."""
    results = {}

    try:
        results['activity_logs'] = cleanup_activity_logs(db)
    except Exception as e:
        results['activity_logs_error'] = str(e)

    try:
        results['agent_runs'] = cleanup_agent_runs(db)
    except Exception as e:
        results['agent_runs_error'] = str(e)

    try:
        results['screenshots'] = cleanup_screenshots()
    except Exception as e:
        results['screenshots_error'] = str(e)

    try:
        results['audit_logs'] = cleanup_audit_logs(db)
    except Exception as e:
        results['audit_logs_error'] = str(e)

    total = sum(v for v in results.values() if isinstance(v, int))
    results['total_deleted'] = total

    if total > 0:
        logger.info(f'Cleanup completed: {results}')

    return results


async def cleanup_loop():
    """Background loop that runs cleanup on schedule."""
    from database import SessionLocal

    # Wait a bit after startup before first cleanup
    await asyncio.sleep(60)

    while True:
        try:
            db = SessionLocal()
            try:
                results = run_cleanup(db)
                if results.get('total_deleted', 0) > 0:
                    logger.info(f'Scheduled cleanup: {results}')
            finally:
                db.close()
        except Exception as e:
            logger.error(f'Cleanup scheduler error: {e}')

        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


def start_cleanup_scheduler():
    """Start the cleanup scheduler as a background asyncio task."""
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(cleanup_loop())
        logger.info(f'Cleanup scheduler started (interval: {CLEANUP_INTERVAL_SECONDS}s)')
    except RuntimeError:
        logger.warning('No event loop — cleanup scheduler not started')


# ===========================================================================
# FastAPI Router — Manual cleanup + retention config endpoints
# ===========================================================================

from fastapi import APIRouter, Depends
from database import get_db

cleanup_router = APIRouter(prefix='/api/admin', tags=['admin'])


@cleanup_router.post('/cleanup')
def trigger_cleanup(db: Session = Depends(get_db)):
    """Manually trigger data cleanup (admin endpoint)."""
    results = run_cleanup(db)
    return {'message': 'Cleanup completed', 'results': results}


@cleanup_router.get('/retention')
def get_retention_config():
    """Get current retention configuration."""
    return {
        'activity_logs_days': RETENTION_ACTIVITY_LOGS_DAYS,
        'agent_runs_days': RETENTION_AGENT_RUNS_DAYS,
        'screenshots_hours': RETENTION_SCREENSHOTS_HOURS,
        'audit_log_days': RETENTION_AUDIT_LOG_DAYS,
        'min_agent_runs_kept': MIN_AGENT_RUNS_KEPT,
        'cleanup_interval_seconds': CLEANUP_INTERVAL_SECONDS,
    }

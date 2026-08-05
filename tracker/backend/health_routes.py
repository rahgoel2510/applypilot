"""Comprehensive health check endpoint for ApplyPilot."""

from fastapi import APIRouter
from datetime import datetime
import time
import os
from pathlib import Path

router = APIRouter(tags=['health'])

_start_time = time.time()


@router.get('/api/health')
def health_check():
    """Comprehensive health check with dependency status."""
    checks = {}
    overall_healthy = True

    # 1. Database check
    try:
        from database import check_database_health
        db_health = check_database_health()
        checks['database'] = {
            'status': db_health['status'],
            'response_time_ms': db_health['response_time_ms'],
            'journal_mode': db_health.get('journal_mode'),
        }
        if db_health['status'] != 'healthy':
            overall_healthy = False
    except Exception as e:
        checks['database'] = {'status': 'unhealthy', 'error': str(e)}
        overall_healthy = False

    # 2. Disk space check
    try:
        import shutil
        total, used, free = shutil.disk_usage('/')
        free_gb = free / (1024**3)
        checks['disk'] = {
            'status': 'healthy' if free_gb > 1.0 else 'warning' if free_gb > 0.5 else 'unhealthy',
            'free_gb': round(free_gb, 2),
            'used_percent': round(used / total * 100, 1),
        }
        if free_gb < 0.5:
            overall_healthy = False
    except Exception as e:
        checks['disk'] = {'status': 'unknown', 'error': str(e)}

    # 3. Agent process check
    try:
        from agent_control import get_controller, AgentState
        controller = get_controller()
        state = controller.status.state
        checks['agent'] = {
            'status': 'running' if state == AgentState.running else 'idle',
            'state': state.value if hasattr(state, 'value') else str(state),
        }
    except Exception as e:
        checks['agent'] = {'status': 'unknown', 'error': str(e)}

    # 4. Browser session check
    try:
        session_paths = [
            Path.home() / '.local' / 'share' / 'linkedin_agent' / 'browser_data',
            Path.home() / 'Library' / 'Application Support' / 'linkedin_agent' / 'browser_data',
        ]
        session_found = any(p.exists() for p in session_paths)
        checks['browser_session'] = {
            'status': 'available' if session_found else 'missing',
            'session_exists': session_found,
        }
    except Exception as e:
        checks['browser_session'] = {'status': 'unknown', 'error': str(e)}

    # 5. Telegram connectivity (just check if token is configured)
    try:
        from database import SessionLocal
        from models import AppSetting
        db = SessionLocal()
        token_setting = db.query(AppSetting).filter(AppSetting.key == 'telegram_bot_token').first()
        env_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        has_token = bool((token_setting and token_setting.value) or env_token)
        checks['telegram'] = {
            'status': 'configured' if has_token else 'not_configured',
            'token_present': has_token,
        }
        db.close()
    except Exception as e:
        checks['telegram'] = {'status': 'unknown', 'error': str(e)}

    # 6. Screenshots directory
    try:
        screenshots_dir = Path(__file__).parent.parent.parent / 'screenshots'
        if screenshots_dir.exists():
            file_count = len(list(screenshots_dir.glob('*.png')))
            checks['screenshots'] = {'status': 'healthy', 'file_count': file_count}
        else:
            checks['screenshots'] = {'status': 'empty', 'file_count': 0}
    except Exception as e:
        checks['screenshots'] = {'status': 'unknown', 'error': str(e)}

    return {
        'status': 'healthy' if overall_healthy else 'degraded',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0',
        'uptime_seconds': int(time.time() - _start_time),
        'checks': checks,
    }

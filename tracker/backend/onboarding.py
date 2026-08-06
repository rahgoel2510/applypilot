"""Onboarding status endpoint — detects if user has configured the app.

Returns a checklist of what's configured and what's missing,
so the frontend can show an onboarding wizard on first visit.
"""

import os
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import AppSetting, AgentRun
from settings_service import get_setting, is_configured

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/status")
def get_onboarding_status(db: Session = Depends(get_db)):
    """Check if the app is configured for first use.
    
    Reads from DB settings (not env vars) to determine configuration status.
    Returns a checklist with completion status for each setup step.
    """
    # Seed settings from env/yaml if not already done
    from settings_routes import _seed_from_sources
    _seed_from_sources(db)
    
    checks = {}
    
    # 1. LinkedIn credentials
    has_linkedin = is_configured('LINKEDIN_EMAIL') and is_configured('LINKEDIN_PASSWORD')
    checks['linkedin_credentials'] = {
        'configured': has_linkedin,
        'label': 'LinkedIn credentials',
        'help': 'Go to Settings → LinkedIn tab and enter your email & password',
    }
    
    # 2. Telegram bot
    has_telegram = is_configured('TELEGRAM_BOT_TOKEN') and is_configured('TELEGRAM_CHAT_ID')
    checks['telegram'] = {
        'configured': has_telegram,
        'label': 'Telegram notifications',
        'help': 'Go to Settings → Telegram tab and enter your bot token & chat ID',
    }
    
    # 3. AI key
    has_ai = is_configured('OPENAI_API_KEY')
    checks['ai_key'] = {
        'configured': has_ai,
        'label': 'AI API key (OpenRouter)',
        'help': 'Go to Settings → AI tab and enter your OpenRouter key (free at openrouter.ai)',
    }
    
    # 4. Candidate info
    has_candidate = is_configured('CANDIDATE_NAME')
    checks['candidate_info'] = {
        'configured': has_candidate,
        'label': 'Candidate profile (name, skills)',
        'help': 'Go to Settings → Candidate tab and fill in your details',
    }
    
    # 5. Job search keywords
    has_keywords = is_configured('SEARCH_KEYWORDS')
    checks['job_keywords'] = {
        'configured': has_keywords,
        'label': 'Job search keywords & locations',
        'help': 'Go to Settings → Job Search tab and set your target roles',
    }
    
    # 6. Resume uploaded
    resume_dir = Path(__file__).parent.parent.parent / 'resumes'
    has_resume = resume_dir.exists() and any(
        f.suffix.lower() in ('.pdf', '.docx', '.doc')
        for f in resume_dir.iterdir()
        if f.is_file() and f.stat().st_size > 100
    )
    checks['resume'] = {
        'configured': has_resume,
        'label': 'Resume uploaded',
        'help': 'Go to Settings → Candidate tab and upload your resume',
    }
    
    # 7. First agent run
    has_run = db.query(AgentRun).filter(
        AgentRun.status.in_(['completed', 'running'])
    ).first() is not None
    checks['first_run'] = {
        'configured': has_run,
        'label': 'First agent run (dry run)',
        'help': 'Go to Agent Control → click Start (with Dry Run ON) to test',
    }
    
    total = len(checks)
    completed = sum(1 for c in checks.values() if c['configured'])
    is_onboarded = completed >= 5
    
    return {
        'is_onboarded': is_onboarded,
        'completed': completed,
        'total': total,
        'progress_percent': round(completed / total * 100),
        'checks': checks,
        'next_step': _get_next_step(checks),
    }


def _get_next_step(checks: dict) -> str | None:
    for check in checks.values():
        if not check['configured']:
            return check['help']
    return None

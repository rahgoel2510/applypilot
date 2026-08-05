"""Onboarding status endpoint — detects if user has configured the app.

Returns a checklist of what's configured and what's missing,
so the frontend can show an onboarding wizard on first visit.
"""

import os
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import AppSetting, Job

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/status")
def get_onboarding_status(db: Session = Depends(get_db)):
    """Check if the app is configured for first use.
    
    Returns a checklist with completion status for each setup step.
    The frontend uses this to show an onboarding prompt if needed.
    """
    checks = {}
    
    # 1. LinkedIn credentials configured
    linkedin_email = os.environ.get("LINKEDIN_EMAIL", "")
    has_linkedin = bool(linkedin_email and linkedin_email != "your-email@gmail.com" and linkedin_email != "your_linkedin_email")
    checks["linkedin_credentials"] = {
        "configured": has_linkedin,
        "label": "LinkedIn credentials",
        "help": "Add LINKEDIN_EMAIL and LINKEDIN_PASSWORD to your .env file",
    }
    
    # 2. Telegram bot configured
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    has_telegram = bool(telegram_token and "your" not in telegram_token.lower())
    checks["telegram"] = {
        "configured": has_telegram,
        "label": "Telegram notifications",
        "help": "Set up a Telegram bot and add token to .env (see README)",
    }
    
    # 3. AI/OpenAI key configured
    ai_key = os.environ.get("OPENAI_API_KEY", "")
    has_ai = bool(ai_key and "your" not in ai_key.lower())
    checks["ai_key"] = {
        "configured": has_ai,
        "label": "AI API key (OpenRouter)",
        "help": "Get a free key at openrouter.ai and add to .env",
    }
    
    # 4. Candidate info in settings DB
    candidate_name = _get_setting(db, "candidate_name")
    has_candidate = bool(candidate_name and candidate_name != "Your Name")
    checks["candidate_info"] = {
        "configured": has_candidate,
        "label": "Candidate profile (name, skills)",
        "help": "Go to Settings → Candidate tab and fill in your details",
    }
    
    # 5. Job search keywords configured
    keywords = _get_setting(db, "job_search_keywords")
    has_keywords = bool(keywords and "your skill" not in keywords.lower())
    checks["job_keywords"] = {
        "configured": has_keywords,
        "label": "Job search keywords & locations",
        "help": "Go to Settings → Job Search tab and set your target roles",
    }
    
    # 6. Resume uploaded
    resume_dir = Path(__file__).parent.parent.parent / "resumes"
    has_resume = resume_dir.exists() and any(
        f.suffix.lower() in (".pdf", ".docx", ".doc")
        for f in resume_dir.iterdir()
        if f.is_file() and f.stat().st_size > 100  # Skip stub files
    )
    checks["resume"] = {
        "configured": has_resume,
        "label": "Resume uploaded",
        "help": "Go to Settings → Candidate tab and upload your resume",
    }
    
    # 7. At least one agent run completed
    from models import AgentRun
    has_run = db.query(AgentRun).filter(AgentRun.status.in_(["completed", "running"])).first() is not None
    checks["first_run"] = {
        "configured": has_run,
        "label": "First agent run",
        "help": "Go to Agent Control → click Start (with Dry Run ON) to test",
    }
    
    # Calculate overall
    total = len(checks)
    completed = sum(1 for c in checks.values() if c["configured"])
    is_onboarded = completed >= 5  # At least 5/7 steps done
    
    return {
        "is_onboarded": is_onboarded,
        "completed": completed,
        "total": total,
        "progress_percent": round(completed / total * 100),
        "checks": checks,
        "next_step": _get_next_step(checks),
    }


def _get_next_step(checks: dict) -> str | None:
    """Return the help text for the first unconfigured item."""
    for check in checks.values():
        if not check["configured"]:
            return check["help"]
    return None


def _get_setting(db: Session, key: str) -> str:
    """Get a setting value from the DB."""
    setting = db.query(AppSetting).filter(AppSetting.key == key).first()
    return setting.value if setting else ""

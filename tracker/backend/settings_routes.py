"""Settings API — stores ALL config in DB, seeded from config.yaml + .env on first run.

On first load:
1. Seeds secrets from .env (TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, etc.)
2. Seeds all config values from config.yaml (candidate, job_search, scheduler, etc.)
3. Frontend reads from DB — always up to date
4. Mandatory fields checked via /api/settings/missing endpoint
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import dotenv_values
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import AppSetting

router = APIRouter(prefix="/api/settings")

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"
CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "config.yaml"

# ===========================================================================
# Full settings schema — ALL fields the app needs
# ===========================================================================

SETTINGS_KEYS = [
    # --- LinkedIn (secrets) ---
    {"key": "LINKEDIN_EMAIL", "label": "LinkedIn Email", "group": "LinkedIn", "placeholder": "your-email@example.com", "required": True, "sensitive": True},
    {"key": "LINKEDIN_PASSWORD", "label": "LinkedIn Password", "group": "LinkedIn", "placeholder": "your-password", "required": True, "sensitive": True},
    # --- Telegram (secrets) ---
    {"key": "TELEGRAM_BOT_TOKEN", "label": "Bot Token", "group": "Telegram", "placeholder": "123456:ABC-DEF...", "required": True, "sensitive": True},
    {"key": "TELEGRAM_CHAT_ID", "label": "Chat ID", "group": "Telegram", "placeholder": "e.g. 123456789", "required": True},
    # --- AI ---
    {"key": "OPENAI_API_KEY", "label": "OpenRouter API Key", "group": "AI", "placeholder": "sk-or-v1-...", "required": False, "sensitive": True},
    {"key": "AI_MODEL", "label": "AI Model", "group": "AI", "placeholder": "openrouter/free", "required": False},
    # --- Candidate ---
    {"key": "CANDIDATE_NAME", "label": "Full Name", "group": "Candidate", "placeholder": "Your Name", "required": True},
    {"key": "CANDIDATE_EMAIL", "label": "Email", "group": "Candidate", "placeholder": "you@example.com", "required": True},
    {"key": "CANDIDATE_PHONE", "label": "Phone", "group": "Candidate", "placeholder": "+91-XXXXXXXXXX", "required": True},
    {"key": "RESUME_FILENAME", "label": "Default Resume", "group": "Candidate", "placeholder": "resume.pdf", "required": True},
    {"key": "NOTICE_PERIOD", "label": "Notice Period", "group": "Candidate", "placeholder": "30 days", "required": False},
    {"key": "WORK_AUTHORIZATION", "label": "Work Authorization", "group": "Candidate", "placeholder": "Authorized to work", "required": False},
    {"key": "WILLING_TO_RELOCATE", "label": "Willing to Relocate", "group": "Candidate", "placeholder": "true", "required": False, "type": "boolean"},
    {"key": "SKILLS", "label": "Skills", "group": "Candidate", "placeholder": "engineering management, system design...", "required": True, "type": "list"},
    {"key": "PREFERRED_CITIES", "label": "Preferred Cities", "group": "Candidate", "placeholder": "Bangalore, Hyderabad, Remote...", "required": False, "type": "list"},
    {"key": "HUMAN_INPUT_TIMEOUT", "label": "Human Input Timeout (sec)", "group": "Candidate", "placeholder": "300", "required": False, "type": "number"},
    {"key": "RESUME_MAPPING", "label": "Resume Mapping", "group": "Candidate", "placeholder": "Keywords | resume.pdf (one per line)", "required": False, "type": "text"},
    {"key": "SENSITIVE_FIELD_ANSWERS", "label": "Pre-configured Answers", "group": "Candidate", "placeholder": "field: answer (one per line)", "required": False, "type": "text"},
    # --- Job Search ---
    {"key": "SEARCH_KEYWORDS", "label": "Keywords", "group": "Job Search", "placeholder": "Engineering Manager, TPM...", "required": True, "type": "list"},
    {"key": "SEARCH_LOCATIONS", "label": "Locations", "group": "Job Search", "placeholder": "India, Bangalore, Remote...", "required": True, "type": "list"},
    {"key": "POSTED_WITHIN", "label": "Posted Within", "group": "Job Search", "placeholder": "24h", "required": False},
    {"key": "INITIAL_SCAN_WINDOW", "label": "First-Run Window", "group": "Job Search", "placeholder": "week", "required": False},
    {"key": "MATCH_THRESHOLD", "label": "Match Threshold (%)", "group": "Job Search", "placeholder": "70", "required": True, "type": "number"},
    {"key": "MAX_POSTINGS_PER_RUN", "label": "Max Jobs per Run", "group": "Job Search", "placeholder": "50", "required": False, "type": "number"},
    {"key": "DAILY_APPLICATION_LIMIT", "label": "Daily Application Cap", "group": "Job Search", "placeholder": "80", "required": False, "type": "number"},
    {"key": "FALLBACK_SCORING", "label": "Fallback Scoring", "group": "Job Search", "placeholder": "true", "required": False, "type": "boolean"},
    {"key": "TRACK_EXTERNAL_APPLY", "label": "Track External Jobs", "group": "Job Search", "placeholder": "true", "required": False, "type": "boolean"},
    {"key": "SKIP_EXTERNAL_APPLY", "label": "Skip External Apply", "group": "Job Search", "placeholder": "false", "required": False, "type": "boolean"},
    # --- Scheduler ---
    {"key": "INTERVAL_MINUTES", "label": "Scan Interval (min)", "group": "Scheduler", "placeholder": "60", "required": False, "type": "number"},
    {"key": "ACTIVE_HOURS_START", "label": "Active From (hour)", "group": "Scheduler", "placeholder": "9", "required": False, "type": "number"},
    {"key": "ACTIVE_HOURS_END", "label": "Active Until (hour)", "group": "Scheduler", "placeholder": "22", "required": False, "type": "number"},
    {"key": "URGENT_MODE", "label": "Urgent Mode", "group": "Scheduler", "placeholder": "true", "required": False, "type": "boolean"},
    {"key": "URGENT_INTERVAL_MINUTES", "label": "Urgent Interval (min)", "group": "Scheduler", "placeholder": "30", "required": False, "type": "number"},
    {"key": "URGENT_MAX_POSTINGS", "label": "Urgent Max Jobs", "group": "Scheduler", "placeholder": "100", "required": False, "type": "number"},
    {"key": "URGENT_DURATION_DAYS", "label": "Urgent Duration (days)", "group": "Scheduler", "placeholder": "7", "required": False, "type": "number"},
    # --- Self-Learning ---
    {"key": "TARGET_COMPANIES", "label": "Target Companies", "group": "Company Preferences", "placeholder": "Google, Microsoft, Amazon...", "required": False, "type": "list"},
    {"key": "BLOCKLIST_COMPANIES", "label": "Blocklist Companies", "group": "Company Preferences", "placeholder": "Wipro, TCS, Infosys...", "required": False, "type": "list"},
    {"key": "TARGET_BOOST", "label": "Target Boost", "group": "Company Preferences", "placeholder": "0.15", "required": False, "type": "number"},
    {"key": "BLOCKLIST_PENALTY", "label": "Blocklist Penalty", "group": "Company Preferences", "placeholder": "0.20", "required": False, "type": "number"},
    # --- InMail ---
    {"key": "INMAIL_ENABLED", "label": "Enable InMail", "group": "InMail", "placeholder": "true", "required": False, "type": "boolean"},
    {"key": "INMAIL_TONE", "label": "Tone", "group": "InMail", "placeholder": "professional", "required": False},
    {"key": "INMAIL_MAX_LENGTH", "label": "Max Length", "group": "InMail", "placeholder": "300", "required": False, "type": "number"},
]

PLACEHOLDER_VALUES = {"placeholder", "placeholder@example.com", "your_bot_token_here"}


def _is_real_value(value: str) -> bool:
    if not value:
        return False
    return value.strip().lower() not in PLACEHOLDER_VALUES and not value.startswith("placeholder")


def _mask_value(key: str, value: str) -> str:
    if not _is_real_value(value):
        return ""
    item = next((i for i in SETTINGS_KEYS if i["key"] == key), {})
    if not item.get("sensitive", False):
        return value  # Non-sensitive values shown as-is
    if "password" in key.lower():
        return "••••••••"
    if len(value) > 12:
        return f"{value[:4]}{'•' * 8}{value[-4:]}"
    return "••••"


# ===========================================================================
# Seed from config.yaml + .env (one-time)
# ===========================================================================

_YAML_TO_DB_MAP = {
    # candidate section
    ("candidate", "name"): "CANDIDATE_NAME",
    ("candidate", "email"): "CANDIDATE_EMAIL",
    ("candidate", "phone"): "CANDIDATE_PHONE",
    ("candidate", "resume_filename"): "RESUME_FILENAME",
    ("candidate", "notice_period"): "NOTICE_PERIOD",
    ("candidate", "work_authorization"): "WORK_AUTHORIZATION",
    ("candidate", "willing_to_relocate"): "WILLING_TO_RELOCATE",
    ("candidate", "skills"): "SKILLS",
    ("candidate", "preferred_cities"): "PREFERRED_CITIES",
    ("candidate", "human_input_timeout"): "HUMAN_INPUT_TIMEOUT",
    ("candidate", "resume_mapping"): "RESUME_MAPPING",
    ("candidate", "sensitive_field_answers"): "SENSITIVE_FIELD_ANSWERS",
    # job_search section
    ("job_search", "keywords"): "SEARCH_KEYWORDS",
    ("job_search", "locations"): "SEARCH_LOCATIONS",
    ("job_search", "posted_within"): "POSTED_WITHIN",
    ("job_search", "initial_scan_window"): "INITIAL_SCAN_WINDOW",
    ("job_search", "match_threshold"): "MATCH_THRESHOLD",
    ("job_search", "max_postings_per_run"): "MAX_POSTINGS_PER_RUN",
    ("job_search", "daily_application_limit"): "DAILY_APPLICATION_LIMIT",
    ("job_search", "fallback_scoring"): "FALLBACK_SCORING",
    ("job_search", "track_external_apply"): "TRACK_EXTERNAL_APPLY",
    ("job_search", "skip_external_apply"): "SKIP_EXTERNAL_APPLY",
    # scheduler section
    ("scheduler", "interval_minutes"): "INTERVAL_MINUTES",
    ("scheduler", "active_hours_start"): "ACTIVE_HOURS_START",
    ("scheduler", "active_hours_end"): "ACTIVE_HOURS_END",
    ("scheduler", "urgent_mode"): "URGENT_MODE",
    ("scheduler", "urgent_interval_minutes"): "URGENT_INTERVAL_MINUTES",
    ("scheduler", "urgent_max_postings"): "URGENT_MAX_POSTINGS",
    ("scheduler", "urgent_duration_days"): "URGENT_DURATION_DAYS",
    # self_learning section
    ("self_learning", "target_companies"): "TARGET_COMPANIES",
    ("self_learning", "blocklist_companies"): "BLOCKLIST_COMPANIES",
    ("self_learning", "target_boost"): "TARGET_BOOST",
    ("self_learning", "blocklist_penalty"): "BLOCKLIST_PENALTY",
    # inmail section
    ("inmail", "enabled"): "INMAIL_ENABLED",
    ("inmail", "tone"): "INMAIL_TONE",
    ("inmail", "max_length"): "INMAIL_MAX_LENGTH",
}


def _serialize_value(value) -> str:
    """Convert any Python value to a string for DB storage."""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return "\n".join(f"{k}: {v}" for k, v in value.items())
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _seed_from_sources(db: Session) -> None:
    """One-time seed: load ALL settings into DB from .env + config.yaml."""
    existing = db.query(AppSetting).count()
    if existing > 0:
        return  # Already seeded

    seeded = False
    valid_keys = {item["key"] for item in SETTINGS_KEYS}
    seen_keys = set()

    # 1. Seed secrets from .env
    if ENV_FILE.exists():
        env_values = dotenv_values(ENV_FILE)
        for key, value in env_values.items():
            if key in valid_keys and value and _is_real_value(value) and key not in seen_keys:
                db.add(AppSetting(key=key, value=value))
                seen_keys.add(key)
                seeded = True

    # Also from os.environ
    for key in valid_keys:
        value = os.environ.get(key, "")
        if value and _is_real_value(value) and key not in seen_keys:
            db.add(AppSetting(key=key, value=value))
            seen_keys.add(key)
            seeded = True

    # 2. Seed config from config.yaml
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}

            for (section, field), db_key in _YAML_TO_DB_MAP.items():
                if db_key in seen_keys:
                    continue
                section_data = yaml_data.get(section, {})
                if not isinstance(section_data, dict):
                    continue
                value = section_data.get(field)
                if value is not None:
                    db.add(AppSetting(key=db_key, value=_serialize_value(value)))
                    seen_keys.add(db_key)
                    seeded = True
        except Exception:
            pass

    if seeded:
        db.commit()


def _get_setting(db: Session, key: str) -> str:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else ""


def _get_all_settings(db: Session) -> dict[str, str]:
    rows = db.query(AppSetting).all()
    return {r.key: r.value for r in rows}


# ===========================================================================
# API Endpoints
# ===========================================================================


class SettingsResponse(BaseModel):
    settings: list[dict]
    configured: int
    total: int


class SettingsUpdateRequest(BaseModel):
    values: dict[str, str]


class SettingsUpdateResponse(BaseModel):
    updated: list[str]
    message: str


@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    """Return all settings with masked/raw values."""
    _seed_from_sources(db)
    all_values = _get_all_settings(db)
    settings = []
    configured_count = 0

    for item in SETTINGS_KEYS:
        key = item["key"]
        raw_value = all_values.get(key, "")
        is_set = _is_real_value(raw_value)
        if is_set:
            configured_count += 1

        settings.append({
            "key": key,
            "label": item["label"],
            "group": item["group"],
            "placeholder": item.get("placeholder", ""),
            "sensitive": item.get("sensitive", False),
            "required": item.get("required", False),
            "type": item.get("type", "text"),
            "masked_value": _mask_value(key, raw_value),
            "current_value": "" if item.get("sensitive") else raw_value,
            "is_set": is_set,
        })

    return SettingsResponse(settings=settings, configured=configured_count, total=len(SETTINGS_KEYS))


@router.put("", response_model=SettingsUpdateResponse)
def update_settings(req: SettingsUpdateRequest, db: Session = Depends(get_db)):
    """Save settings to DB."""
    valid_keys = {item["key"] for item in SETTINGS_KEYS}
    updated = []

    for key, value in req.values.items():
        if key not in valid_keys:
            continue
        if not value.strip():
            continue
        existing = db.query(AppSetting).filter(AppSetting.key == key).first()
        if existing:
            existing.value = value.strip()
        else:
            db.add(AppSetting(key=key, value=value.strip()))
        updated.append(key)

    db.commit()
    return SettingsUpdateResponse(
        updated=updated,
        message=f"Saved {len(updated)} setting(s)." if updated else "No changes.",
    )


@router.get("/missing")
def get_missing_settings(db: Session = Depends(get_db)):
    """Return list of required settings that are not configured.
    
    Frontend uses this to show a mandatory-fields popup on first visit.
    """
    _seed_from_sources(db)
    all_values = _get_all_settings(db)
    missing = []

    for item in SETTINGS_KEYS:
        if not item.get("required"):
            continue
        key = item["key"]
        value = all_values.get(key, "")
        if not _is_real_value(value):
            missing.append({
                "key": key,
                "label": item["label"],
                "group": item["group"],
                "placeholder": item.get("placeholder", ""),
            })

    return {"missing": missing, "count": len(missing), "all_configured": len(missing) == 0}


@router.get("/env")
def get_settings_as_env(db: Session = Depends(get_db)):
    """Internal: returns all settings as key-value for the agent subprocess."""
    _seed_from_sources(db)
    return _get_all_settings(db)


# ===========================================================================
# Config YAML read/write (kept for backward compat with CLI)
# ===========================================================================


@router.get("/config")
def get_config_yaml():
    """Return config.yaml as JSON (backward compat)."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@router.put("/config")
def update_config_yaml(config: dict):
    """Write to config.yaml (backward compat for CLI users)."""
    try:
        existing = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        for section, values in config.items():
            if isinstance(values, dict) and section in existing and isinstance(existing[section], dict):
                existing[section].update(values)
            else:
                existing[section] = values
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(existing, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return {"message": "Config saved"}
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# Test Connection
# ===========================================================================

import httpx as httpx_client


class TestResult(BaseModel):
    success: bool
    message: str


@router.post("/test/telegram", response_model=TestResult)
def test_telegram(db: Session = Depends(get_db)):
    """Test Telegram bot connection."""
    _seed_from_sources(db)
    token = _get_setting(db, "TELEGRAM_BOT_TOKEN")
    chat_id = _get_setting(db, "TELEGRAM_CHAT_ID")

    if not _is_real_value(token):
        return TestResult(success=False, message="Bot token not configured.")
    if not _is_real_value(chat_id):
        return TestResult(success=False, message="Chat ID not configured.")

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = httpx_client.post(url, json={"chat_id": chat_id, "text": "✅ ApplyPilot test — connection working!"}, timeout=10)
        if resp.status_code == 200:
            return TestResult(success=True, message="Message sent!")
        else:
            data = resp.json()
            return TestResult(success=False, message=data.get("description", f"HTTP {resp.status_code}"))
    except Exception as e:
        return TestResult(success=False, message=str(e)[:100])


@router.post("/test/openai", response_model=TestResult)
def test_openai(db: Session = Depends(get_db)):
    """Test OpenRouter/AI connection."""
    _seed_from_sources(db)
    api_key = _get_setting(db, "OPENAI_API_KEY")
    if not _is_real_value(api_key):
        return TestResult(success=False, message="API key not configured.")
    try:
        resp = httpx_client.get("https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        if resp.status_code == 200:
            return TestResult(success=True, message="OpenRouter connected!")
        return TestResult(success=False, message=f"HTTP {resp.status_code}")
    except Exception as e:
        return TestResult(success=False, message=str(e)[:100])


@router.post("/test/linkedin", response_model=TestResult)
def test_linkedin(db: Session = Depends(get_db)):
    """Check if LinkedIn session exists."""
    _seed_from_sources(db)
    return _check_session(db)


def _check_session(db: Session) -> TestResult:
    from platformdirs import user_data_dir
    data_dir = Path(user_data_dir("linkedin_agent", "linkedin_agent")) / "browser_data"
    if data_dir.exists() and any(data_dir.iterdir()):
        return TestResult(success=True, message="Browser session exists (cookies saved).")
    return TestResult(success=False, message="No saved session. Run the agent once to create one.")


@router.get("/models")
def list_free_models():
    """Return available free models from OpenRouter."""
    try:
        resp = httpx_client.get("https://openrouter.ai/api/v1/models", timeout=10)
        if resp.status_code != 200:
            return []
        models = resp.json().get("data", [])
        free = [m for m in models if m.get("pricing", {}).get("prompt") == "0"]
        return [{"id": m["id"], "name": m.get("name", m["id"])} for m in free[:20]]
    except Exception:
        return []

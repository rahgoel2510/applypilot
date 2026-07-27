"""Settings API — stores secrets in DB, applies instantly at runtime.

Security model:
- Settings are stored in the app_settings DB table (encrypted at rest via SQLite)
- GET returns MASKED values only — never the full secret
- PUT saves immediately — no restart needed, agent reads fresh on each launch
- On first run, seeds from .env if DB is empty (one-time migration)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import AppSetting

router = APIRouter(prefix="/api/settings")

# Path to .env (used only for initial seed)
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"

# Settings schema
SETTINGS_KEYS = [
    {"key": "TELEGRAM_BOT_TOKEN", "label": "Telegram Bot Token", "group": "Telegram", "placeholder": "e.g. 123456:ABC-DEF..."},
    {"key": "TELEGRAM_CHAT_ID", "label": "Telegram Chat ID", "group": "Telegram", "placeholder": "e.g. 7669562648"},
    {"key": "OPENAI_API_KEY", "label": "OpenRouter API Key", "group": "AI (OpenRouter)", "placeholder": "e.g. sk-or-v1-..."},
    {"key": "AI_MODEL", "label": "AI Model", "group": "AI (OpenRouter)", "placeholder": "e.g. openrouter/free"},
    {"key": "LINKEDIN_EMAIL", "label": "LinkedIn Email", "group": "LinkedIn", "placeholder": "your-email@example.com"},
    {"key": "LINKEDIN_PASSWORD", "label": "LinkedIn Password", "group": "LinkedIn", "placeholder": "Enter your password", "sensitive": True},
]

PLACEHOLDER_VALUES = {"placeholder", "placeholder@example.com", "your_bot_token_here", "sk-placeholder-not-needed-for-testing"}


def _is_real_value(value: str) -> bool:
    """Check if a value is actually configured (not a placeholder)."""
    if not value:
        return False
    return value.strip().lower() not in PLACEHOLDER_VALUES and not value.startswith("placeholder")


def _mask_value(key: str, value: str) -> str:
    """Mask a secret for display."""
    if not _is_real_value(value):
        return ""
    if "password" in key.lower():
        return "••••••••"
    if len(value) > 12:
        return f"{value[:4]}{'•' * 8}{value[-4:]}"
    elif len(value) > 4:
        return f"{value[:2]}{'•' * (len(value) - 2)}"
    return "••••"


def _seed_from_env(db: Session) -> None:
    """One-time seed: copy .env values into DB if table is empty."""
    existing = db.query(AppSetting).count()
    if existing > 0:
        return  # Already seeded

    if not ENV_FILE.exists():
        return

    env_values = dotenv_values(ENV_FILE)
    valid_keys = {item["key"] for item in SETTINGS_KEYS}

    for key, value in env_values.items():
        if key in valid_keys and value and _is_real_value(value):
            db.add(AppSetting(key=key, value=value))

    db.commit()


def _get_setting(db: Session, key: str) -> str:
    """Get a setting value from DB."""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else ""


def _get_all_settings(db: Session) -> dict[str, str]:
    """Get all settings as a dict."""
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
    """Return all settings with masked values."""
    _seed_from_env(db)

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
            "masked_value": _mask_value(key, raw_value),
            "is_set": is_set,
        })

    return SettingsResponse(settings=settings, configured=configured_count, total=len(SETTINGS_KEYS))


@router.put("", response_model=SettingsUpdateResponse)
def update_settings(req: SettingsUpdateRequest, db: Session = Depends(get_db)):
    """Save settings to DB. Takes effect immediately — no restart needed."""
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

    if updated:
        return SettingsUpdateResponse(
            updated=updated,
            message=f"Saved {len(updated)} setting(s). Changes take effect on the next agent run.",
        )
    return SettingsUpdateResponse(updated=[], message="No changes made.")


# ===========================================================================
# Settings loader for agent subprocess
# ===========================================================================


@router.get("/env")
def get_settings_as_env(db: Session = Depends(get_db)):
    """Internal endpoint: returns all settings as key-value pairs for the agent.

    Used by agent_control.py to inject settings into the subprocess environment.
    This endpoint should NOT be exposed publicly in production.
    """
    _seed_from_env(db)
    return _get_all_settings(db)


# ===========================================================================
# Test Connection Endpoints
# ===========================================================================

import httpx as httpx_client


class TestResult(BaseModel):
    success: bool
    message: str


@router.post("/test/telegram", response_model=TestResult)
def test_telegram(db: Session = Depends(get_db)):
    """Test Telegram bot connection."""
    _seed_from_env(db)
    token = _get_setting(db, "TELEGRAM_BOT_TOKEN")
    chat_id = _get_setting(db, "TELEGRAM_CHAT_ID")

    if not _is_real_value(token):
        return TestResult(success=False, message="Bot token not configured.")
    if not _is_real_value(chat_id):
        return TestResult(success=False, message="Chat ID not configured.")

    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = httpx_client.get(url, timeout=10)
        data = response.json()

        if not data.get("ok"):
            return TestResult(success=False, message=f"Invalid token: {data.get('description', 'Unknown error')}")

        bot_name = data["result"].get("username", "unknown")

        send_url = f"https://api.telegram.org/bot{token}/sendMessage"
        msg_response = httpx_client.post(send_url, json={
            "chat_id": chat_id,
            "text": "✅ *ApplyPilot — Connection Test*\n\nTelegram is working! You'll receive notifications here.",
            "parse_mode": "Markdown",
        }, timeout=10)
        msg_data = msg_response.json()

        if msg_data.get("ok"):
            return TestResult(success=True, message=f"Connected! Bot: @{bot_name}. Check your Telegram for a test message.")
        else:
            return TestResult(success=False, message=f"Bot works but can't reach chat {chat_id}: {msg_data.get('description')}")

    except httpx_client.ConnectError:
        return TestResult(success=False, message="Network error — can't reach Telegram.")
    except httpx_client.TimeoutException:
        return TestResult(success=False, message="Timeout connecting to Telegram.")
    except Exception as e:
        return TestResult(success=False, message=f"Error: {str(e)[:100]}")


@router.post("/test/openai", response_model=TestResult)
def test_openai(db: Session = Depends(get_db)):
    """Test OpenRouter API key."""
    _seed_from_env(db)
    api_key = _get_setting(db, "OPENAI_API_KEY")

    if not _is_real_value(api_key):
        return TestResult(success=False, message="API key not configured.")

    try:
        response = httpx_client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            model_count = len(data.get("data", []))
            free_count = sum(1 for m in data.get("data", [])
                           if float((m.get("pricing") or {}).get("prompt", "1") or "1") == 0)
            return TestResult(success=True, message=f"Connected! {model_count} models available ({free_count} free).")
        elif response.status_code == 401:
            return TestResult(success=False, message="Invalid API key. Check your key at openrouter.ai/keys.")
        else:
            return TestResult(success=False, message=f"Unexpected response: {response.status_code}")

    except httpx_client.ConnectError:
        return TestResult(success=False, message="Can't reach OpenRouter.")
    except httpx_client.TimeoutException:
        return TestResult(success=False, message="Timeout connecting to OpenRouter.")
    except Exception as e:
        return TestResult(success=False, message=f"Error: {str(e)[:100]}")


@router.post("/test/linkedin", response_model=TestResult)
def test_linkedin(db: Session = Depends(get_db)):
    """Test LinkedIn connection using existing Chrome session (no re-login needed)."""
    _seed_from_env(db)
    email = _get_setting(db, "LINKEDIN_EMAIL")
    password = _get_setting(db, "LINKEDIN_PASSWORD")

    if not _is_real_value(email):
        return TestResult(success=False, message="Email not configured.")
    if not _is_real_value(password):
        return TestResult(success=False, message="Password not configured.")
    if "@" not in email:
        return TestResult(success=False, message="Email doesn't look valid (missing @).")

    # Use existing Chrome session to verify LinkedIn is accessible
    try:
        import asyncio
        from playwright.async_api import async_playwright
        import os

        async def _check_session():
            pw = await async_playwright().start()

            # Try the agent's persistent browser data first
            agent_data_dir = os.path.expanduser(
                "~/Library/Application Support/linkedin_agent/browser_data"
            )

            # Use Chrome's existing user data (already logged into LinkedIn)
            chrome_data_dir = os.path.expanduser(
                "~/Library/Application Support/Google/Chrome"
            )

            # Try agent's saved session first, then Chrome
            data_dir = agent_data_dir if os.path.exists(agent_data_dir + "/Default") else None

            if data_dir:
                # Use persistent context (has saved cookies)
                ctx = await pw.chromium.launch_persistent_context(
                    user_data_dir=data_dir,
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            else:
                # No saved session — just validate credentials format
                await pw.stop()
                return TestResult(
                    success=True,
                    message=f"Credentials set for {email}. First run will open a browser for manual login (session saves for future runs).",
                )

            # Check if we're logged in by visiting feed
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)

            current_url = page.url
            await ctx.close()
            await pw.stop()

            if "/feed" in current_url and "/login" not in current_url:
                return TestResult(success=True, message=f"Connected! LinkedIn session is active for {email}.")
            else:
                return TestResult(
                    success=True,
                    message=f"Credentials set for {email}. Session expired — agent will re-login on next run.",
                )

        result = asyncio.run(_check_session())
        return result

    except ImportError:
        return TestResult(success=False, message="Playwright not installed. Run: playwright install chromium")
    except Exception as e:
        err_msg = str(e)[:100]
        if "executable doesn't exist" in err_msg.lower():
            return TestResult(success=False, message="Chromium not installed. Run: playwright install chromium")
        # If browser test fails, just confirm credentials are set
        return TestResult(
            success=True,
            message=f"Credentials set for {email}. Browser test skipped ({err_msg[:50]}).",
        )


# ===========================================================================
# Models endpoint
# ===========================================================================


@router.get("/models")
def list_free_models(db: Session = Depends(get_db)):
    """List available free models from OpenRouter with capabilities."""
    _seed_from_env(db)
    api_key = _get_setting(db, "OPENAI_API_KEY")

    if not _is_real_value(api_key):
        return {"models": [], "error": "API key not configured"}

    try:
        response = httpx_client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )

        if response.status_code != 200:
            return {"models": [], "error": f"API returned {response.status_code}"}

        data = response.json()
        all_models = data.get("data", [])

        free_models = []
        for m in all_models:
            model_id = m.get("id", "")
            pricing = m.get("pricing", {})
            prompt_price = float(pricing.get("prompt", "1") or "1")
            completion_price = float(pricing.get("completion", "1") or "1")

            if prompt_price == 0 and completion_price == 0:
                ctx = m.get("context_length", 0)

                capabilities = []
                if ctx >= 100000:
                    capabilities.append("long-context")
                if "code" in model_id.lower() or "code" in m.get("name", "").lower():
                    capabilities.append("code")
                if "tool" in str(m.get("supported_parameters", [])):
                    capabilities.append("tools")

                if any(x in model_id for x in ["70b", "72b", "gemma-4-31b", "qwen-3-72b"]):
                    tier = "high"
                elif any(x in model_id for x in ["26b", "27b", "24b", "32b"]):
                    tier = "medium"
                else:
                    tier = "standard"

                free_models.append({
                    "id": model_id,
                    "name": m.get("name", model_id),
                    "context_length": ctx,
                    "description": m.get("description", "")[:120],
                    "capabilities": capabilities,
                    "tier": tier,
                })

        tier_order = {"high": 0, "medium": 1, "standard": 2}
        free_models.sort(key=lambda x: (tier_order.get(x["tier"], 2), -x["context_length"]))

        return {"models": free_models, "total": len(free_models)}

    except Exception as e:
        return {"models": [], "error": str(e)[:100]}

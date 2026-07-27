"""Settings API — securely manage .env secrets from the UI.

Security model:
- GET /api/settings returns MASKED values (e.g., "sk-proj...****")
- PUT /api/settings accepts new values and writes to .env
- Values are NEVER returned in full to the frontend
- Empty string means "unchanged" (keeps existing value)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values, set_key
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings")

# Path to the .env file (project root)
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"

# Settings schema — all the configurable secrets/keys
SETTINGS_KEYS = [
    {"key": "TELEGRAM_BOT_TOKEN", "label": "Telegram Bot Token", "group": "Telegram", "placeholder": "e.g. 123456:ABC-DEF..."},
    {"key": "TELEGRAM_CHAT_ID", "label": "Telegram Chat ID", "group": "Telegram", "placeholder": "e.g. 7669562648"},
    {"key": "OPENAI_API_KEY", "label": "OpenRouter API Key", "group": "AI (OpenRouter)", "placeholder": "e.g. sk-or-v1-..."},
    {"key": "AI_MODEL", "label": "AI Model", "group": "AI (OpenRouter)", "placeholder": "e.g. openrouter/free"},
    {"key": "LINKEDIN_EMAIL", "label": "LinkedIn Email", "group": "LinkedIn", "placeholder": "your-email@example.com"},
    {"key": "LINKEDIN_PASSWORD", "label": "LinkedIn Password", "group": "LinkedIn", "placeholder": "••••••••", "sensitive": True},
]


def _mask_value(key: str, value: str) -> str:
    """Mask a secret value for display — never expose the full thing."""
    if not value or value.startswith("placeholder") or value == "your_bot_token_here":
        return ""  # Not configured

    if "password" in key.lower():
        return "••••••••" if value else ""

    # Show first 4 + last 4 chars for tokens/keys
    if len(value) > 12:
        return f"{value[:4]}{'•' * 8}{value[-4:]}"
    elif len(value) > 4:
        return f"{value[:2]}{'•' * (len(value) - 2)}"
    else:
        return "••••"


def _load_env() -> dict[str, str]:
    """Load current .env values."""
    if not ENV_FILE.exists():
        return {}
    return dotenv_values(ENV_FILE)


class SettingsResponse(BaseModel):
    settings: list[dict]
    configured: int
    total: int


class SettingsUpdateRequest(BaseModel):
    values: dict[str, str]  # key -> new value (empty string = no change)


class SettingsUpdateResponse(BaseModel):
    updated: list[str]
    message: str


@router.get("", response_model=SettingsResponse)
def get_settings():
    """Return all settings with masked values. Never exposes full secrets."""
    env_values = _load_env()
    settings = []
    configured_count = 0

    for item in SETTINGS_KEYS:
        key = item["key"]
        raw_value = env_values.get(key, "")
        masked = _mask_value(key, raw_value)
        is_set = bool(raw_value) and not raw_value.startswith("placeholder") and raw_value != "your_bot_token_here"

        if is_set:
            configured_count += 1

        settings.append({
            "key": key,
            "label": item["label"],
            "group": item["group"],
            "placeholder": item.get("placeholder", ""),
            "sensitive": item.get("sensitive", False),
            "masked_value": masked,
            "is_set": is_set,
        })

    return SettingsResponse(
        settings=settings,
        configured=configured_count,
        total=len(SETTINGS_KEYS),
    )


@router.put("", response_model=SettingsUpdateResponse)
def update_settings(req: SettingsUpdateRequest):
    """Update .env settings. Only non-empty values are written."""
    # Ensure .env file exists
    if not ENV_FILE.exists():
        ENV_FILE.write_text("# ApplyPilot Configuration\n")

    valid_keys = {item["key"] for item in SETTINGS_KEYS}
    updated = []

    for key, value in req.values.items():
        # Only accept known keys
        if key not in valid_keys:
            continue
        # Empty string means "no change"
        if not value.strip():
            continue

        # Write to .env file
        set_key(str(ENV_FILE), key, value.strip())
        updated.append(key)

    if updated:
        return SettingsUpdateResponse(
            updated=updated,
            message=f"Updated {len(updated)} setting(s). Restart the agent for changes to take effect.",
        )
    else:
        return SettingsUpdateResponse(
            updated=[],
            message="No changes made.",
        )


# ===========================================================================
# Test Connection Endpoints
# ===========================================================================

import asyncio
import httpx as httpx_client


class TestResult(BaseModel):
    success: bool
    message: str


@router.post("/test/telegram", response_model=TestResult)
def test_telegram():
    """Test Telegram bot connection by sending a test message."""
    env_values = _load_env()
    token = env_values.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env_values.get("TELEGRAM_CHAT_ID", "")

    if not token or token.startswith("placeholder") or token == "your_bot_token_here":
        return TestResult(success=False, message="Bot token not configured. Please set it first.")
    if not chat_id or chat_id.startswith("placeholder"):
        return TestResult(success=False, message="Chat ID not configured. Please set it first.")

    try:
        # Call Telegram getMe API
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = httpx_client.get(url, timeout=10)
        data = response.json()

        if not data.get("ok"):
            return TestResult(success=False, message=f"Invalid token: {data.get('description', 'Unknown error')}")

        bot_name = data["result"].get("username", "unknown")

        # Send a test message
        send_url = f"https://api.telegram.org/bot{token}/sendMessage"
        msg_response = httpx_client.post(send_url, json={
            "chat_id": chat_id,
            "text": "✅ *ApplyPilot — Connection Test*\n\nTelegram is configured correctly!",
            "parse_mode": "Markdown",
        }, timeout=10)
        msg_data = msg_response.json()

        if msg_data.get("ok"):
            return TestResult(success=True, message=f"Connected! Bot: @{bot_name}. Test message sent to your chat.")
        else:
            return TestResult(success=False, message=f"Bot works but can't message chat {chat_id}: {msg_data.get('description')}")

    except httpx_client.ConnectError:
        return TestResult(success=False, message="Network error — can't reach Telegram API.")
    except httpx_client.TimeoutException:
        return TestResult(success=False, message="Timeout — Telegram API not responding.")
    except Exception as e:
        return TestResult(success=False, message=f"Error: {str(e)[:100]}")


@router.post("/test/openai", response_model=TestResult)
def test_openai():
    """Test OpenRouter API key (OpenAI-compatible) by listing models."""
    env_values = _load_env()
    api_key = env_values.get("OPENAI_API_KEY", "")

    if not api_key or api_key.startswith("placeholder") or api_key.startswith("sk-placeholder"):
        return TestResult(success=False, message="API key not configured. Please set it first.")

    try:
        # OpenRouter uses the same /v1/models endpoint
        response = httpx_client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            model_count = len(data.get("data", []))
            free_models = [m for m in data.get("data", []) if ":free" in m.get("id", "")]
            return TestResult(
                success=True,
                message=f"Connected to OpenRouter! {model_count} models available ({len(free_models)} free).",
            )
        elif response.status_code == 401:
            return TestResult(success=False, message="Invalid API key. Please check and re-enter.")
        elif response.status_code == 429:
            return TestResult(success=True, message="Key is valid but rate-limited. Try again later.")
        else:
            return TestResult(success=False, message=f"Unexpected response: {response.status_code}")

    except httpx_client.ConnectError:
        return TestResult(success=False, message="Network error — can't reach OpenRouter API.")
    except httpx_client.TimeoutException:
        return TestResult(success=False, message="Timeout — OpenRouter API not responding.")
    except Exception as e:
        return TestResult(success=False, message=f"Error: {str(e)[:100]}")


@router.get("/models")
def list_free_models():
    """List available free models from OpenRouter."""
    env_values = _load_env()
    api_key = env_values.get("OPENAI_API_KEY", "")

    if not api_key or api_key.startswith("placeholder"):
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

        # Filter free models and format them
        free_models = []
        for m in all_models:
            model_id = m.get("id", "")
            pricing = m.get("pricing", {})
            prompt_price = float(pricing.get("prompt", "1") or "1")
            completion_price = float(pricing.get("completion", "1") or "1")

            if prompt_price == 0 and completion_price == 0:
                free_models.append({
                    "id": model_id,
                    "name": m.get("name", model_id),
                    "context_length": m.get("context_length", 0),
                })

        # Sort by name
        free_models.sort(key=lambda x: x["name"])

        return {"models": free_models, "total": len(free_models)}

    except Exception as e:
        return {"models": [], "error": str(e)[:100]}


@router.post("/test/linkedin", response_model=TestResult)
def test_linkedin():
    """Validate LinkedIn credentials are set (can't actually test login without browser)."""
    env_values = _load_env()
    email = env_values.get("LINKEDIN_EMAIL", "")
    password = env_values.get("LINKEDIN_PASSWORD", "")

    if not email or email.startswith("placeholder"):
        return TestResult(success=False, message="LinkedIn email not configured.")
    if not password or password == "placeholder":
        return TestResult(success=False, message="LinkedIn password not configured.")

    # We can't actually test LinkedIn login without launching a browser,
    # so just validate the format and confirm they're set.
    if "@" not in email:
        return TestResult(success=False, message="Email doesn't look valid (missing @).")

    return TestResult(
        success=True,
        message=f"Credentials set for {email}. Login will be tested when agent launches.",
    )

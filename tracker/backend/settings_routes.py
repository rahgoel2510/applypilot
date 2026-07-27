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
    {"key": "OPENAI_API_KEY", "label": "OpenAI API Key", "group": "AI", "placeholder": "e.g. sk-proj-..."},
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

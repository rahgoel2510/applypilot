"""Auto-repair engine — uses LLM to diagnose agent failures and suggest/apply fixes.

When the agent fails, this module:
1. Sends the error + context to OpenRouter
2. Gets a structured diagnosis (cause, fix, retry params)
3. Applies the fix and retries automatically

Uses free models via OpenRouter API.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import AppSetting

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DIAGNOSIS_SYSTEM_PROMPT = """\
You are an expert DevOps engineer and Python automation specialist. 
Your job is to analyze agent pipeline failures and provide actionable fixes.

The agent is "ApplyPilot" — a LinkedIn job application automation tool that uses:
- Playwright (headless Chromium) for browser automation
- Python asyncio for orchestration
- LinkedIn's web interface (selectors may change)
- Telegram bot for notifications

When given an error log, respond with EXACTLY this JSON structure:
{
  "diagnosis": "One-sentence root cause explanation",
  "severity": "low|medium|high|critical",
  "category": "session|selector|network|timeout|config|permission|unknown",
  "fix_description": "What needs to be done to fix this",
  "auto_fixable": true/false,
  "retry_params": {
    "skip_login": true/false,
    "increase_timeout": true/false,
    "timeout_multiplier": 2,
    "use_js_fallback": true/false,
    "headless": true/false
  },
  "user_action_required": "What the user needs to do manually (if auto_fixable is false)",
  "confidence": 0.0-1.0
}

Common issues you'll see:
- "element is not visible" → LinkedIn changed their UI or session is invalid
- "Timeout exceeded" → slow network or bot detection
- "session expired" → cookies invalid, need fresh session
- "Can't parse entities" → error message has HTML in Telegram notification
- "Executable doesn't exist" → Playwright/Chromium not installed properly

Be precise. Don't guess. If you're not sure, set confidence low and auto_fixable to false.
"""


class DiagnosisResult(BaseModel):
    diagnosis: str
    severity: str = "medium"
    category: str = "unknown"
    fix_description: str
    auto_fixable: bool = False
    retry_params: dict = {}
    user_action_required: str = ""
    confidence: float = 0.5
    model_used: str = ""
    raw_response: str = ""


class RepairResult(BaseModel):
    diagnosed: bool
    diagnosis: Optional[DiagnosisResult] = None
    retried: bool = False
    retry_success: bool = False
    message: str


def _get_api_key() -> str:
    """Get OpenRouter API key from DB."""
    db = SessionLocal()
    try:
        row = db.query(AppSetting).filter(AppSetting.key == "OPENAI_API_KEY").first()
        return row.value if row else ""
    finally:
        db.close()


def _get_model() -> str:
    """Get configured AI model from DB."""
    db = SessionLocal()
    try:
        row = db.query(AppSetting).filter(AppSetting.key == "AI_MODEL").first()
        return row.value if row and row.value else "openrouter/free"
    finally:
        db.close()


def diagnose_error(error_log: str, last_output: str = "") -> DiagnosisResult:
    """Send error to LLM for diagnosis.

    Args:
        error_log: The error message/traceback
        last_output: Last N lines of agent stdout for context

    Returns:
        DiagnosisResult with fix suggestions
    """
    api_key = _get_api_key()
    if not api_key:
        return DiagnosisResult(
            diagnosis="Cannot diagnose — no OpenRouter API key configured.",
            fix_description="Set your OpenRouter API key in Settings.",
            user_action_required="Go to Settings → AI (OpenRouter) → enter your API key.",
        )

    model = _get_model()

    # Build the user prompt with error context
    user_prompt = f"""Analyze this agent failure and provide a structured diagnosis.

ERROR:
{error_log[:2000]}

LAST OUTPUT (context):
{last_output[-3000:] if last_output else "No output captured"}

Respond with ONLY the JSON structure. No markdown, no explanation outside the JSON."""

    try:
        response = httpx.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 800,
            },
            timeout=30,
        )

        if response.status_code != 200:
            return DiagnosisResult(
                diagnosis=f"LLM API returned {response.status_code}",
                fix_description="Check API key and model availability.",
                raw_response=response.text[:200],
            )

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Parse JSON from response
        try:
            # Strip markdown code blocks if present
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed = json.loads(clean)

            return DiagnosisResult(
                diagnosis=parsed.get("diagnosis", "Unknown error"),
                severity=parsed.get("severity", "medium"),
                category=parsed.get("category", "unknown"),
                fix_description=parsed.get("fix_description", ""),
                auto_fixable=parsed.get("auto_fixable", False),
                retry_params=parsed.get("retry_params", {}),
                user_action_required=parsed.get("user_action_required", ""),
                confidence=parsed.get("confidence", 0.5),
                model_used=model,
                raw_response=content[:500],
            )
        except json.JSONDecodeError:
            return DiagnosisResult(
                diagnosis="LLM response was not valid JSON",
                fix_description=content[:200],
                raw_response=content[:500],
                model_used=model,
            )

    except httpx.ConnectError:
        return DiagnosisResult(
            diagnosis="Cannot reach OpenRouter API.",
            fix_description="Check internet connection.",
        )
    except httpx.TimeoutException:
        return DiagnosisResult(
            diagnosis="OpenRouter API timed out.",
            fix_description="Try again or use a different model.",
        )
    except Exception as e:
        return DiagnosisResult(
            diagnosis=f"Diagnosis failed: {str(e)[:100]}",
            fix_description="Check the auto-repair module logs.",
        )


def build_retry_params(diagnosis: DiagnosisResult, original_config: dict) -> dict:
    """Build adjusted parameters for a retry based on the diagnosis.

    Args:
        diagnosis: The LLM diagnosis result
        original_config: The original trigger config

    Returns:
        Adjusted config dict for retrying
    """
    new_config = dict(original_config)
    retry = diagnosis.retry_params

    if retry.get("skip_login"):
        new_config["skip_login"] = True

    if retry.get("increase_timeout"):
        multiplier = retry.get("timeout_multiplier", 2)
        new_config["timeout_multiplier"] = multiplier

    if retry.get("use_js_fallback"):
        new_config["use_js_fallback"] = True

    if "headless" in retry:
        new_config["headless"] = retry["headless"]

    return new_config

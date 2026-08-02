"""ApplyPilot Telegram Command Bot — Remote trigger, tracker, and activity monitor.

Features:
- /run_agent <limit> — ping device, then trigger scan
- /status — show current agent state + last run summary
- /track_status — show Kanban board summary
- /logs [run_id] — GitHub Actions-style formatted run logs
- /schedule — show/set scheduler config
- /ping — check if machine is reachable

Requires: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in settings.
Run: python -m linkedin_agent.bot
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

# Config
TRACKER_URL = os.environ.get("TRACKER_URL", "http://127.0.0.1:8000")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


async def api_get(path: str) -> dict | None:
    """GET request to tracker API."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{TRACKER_URL}{path}")
            return r.json() if r.status_code == 200 else None
    except Exception:
        return None


async def api_post(path: str, data: dict = None) -> dict | None:
    """POST request to tracker API."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{TRACKER_URL}{path}", json=data or {})
            return r.json() if r.status_code in (200, 201) else None
    except Exception:
        return None


def is_authorized(update: Update) -> bool:
    """Only allow commands from the configured chat."""
    return str(update.effective_chat.id) == ALLOWED_CHAT_ID


# ═══════════════════════════════════════════════════════════════
# /ping — Device heartbeat check
# ═══════════════════════════════════════════════════════════════


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check if the local machine is reachable."""
    if not is_authorized(update):
        return

    msg = await update.message.reply_text("🔍 Pinging local machine...")

    result = await api_get("/api/stats")
    if result is not None:
        await msg.edit_text(
            "🟢 *Machine is ONLINE*\n\n"
            f"Tracker API: `{TRACKER_URL}`\n"
            f"Response: ✓ Connected\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await msg.edit_text(
            "🔴 *Machine is OFFLINE*\n\n"
            f"Cannot reach `{TRACKER_URL}`\n"
            "Make sure Docker is running and the tracker is up.",
            parse_mode=ParseMode.MARKDOWN,
        )


# ═══════════════════════════════════════════════════════════════
# /run_agent — Ping + trigger agent
# ═══════════════════════════════════════════════════════════════


async def cmd_run_agent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ping device, then trigger the agent."""
    if not is_authorized(update):
        return

    # Parse args
    args = context.args or []
    limit = int(args[0]) if args and args[0].isdigit() else 10
    dry_run = "--apply" not in " ".join(args)

    mode_str = "DRY RUN" if dry_run else "LIVE (will apply)"
    msg = await update.message.reply_text(
        f"⏳ *Starting scan*\n"
        f"Mode: {mode_str} | Limit: {limit}\n\n"
        f"Step 1/3: Checking machine status...",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Step 1: Ping
    ping_result = await api_get("/api/stats")
    if ping_result is None:
        await msg.edit_text(
            "🔴 *Cannot start — machine is offline*\n\n"
            f"Tracker at `{TRACKER_URL}` is not responding.\n"
            "Start Docker and try again.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await msg.edit_text(
        f"⏳ *Starting scan*\n"
        f"Mode: {mode_str} | Limit: {limit}\n\n"
        f"🟢 Step 1/3: Machine online ✓\n"
        f"⏳ Step 2/3: Triggering agent...",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Step 2: Trigger
    trigger_result = await api_post("/api/agent/trigger", {
        "mode": "single",
        "dry_run": dry_run,
        "limit": limit,
    })

    if not trigger_result or "error" in trigger_result:
        error = trigger_result.get("error", "Unknown error") if trigger_result else "API unreachable"
        await msg.edit_text(
            f"🔴 *Agent trigger failed*\n\n"
            f"Error: `{error}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await msg.edit_text(
        f"✅ *Agent triggered*\n\n"
        f"🟢 Step 1/3: Machine online ✓\n"
        f"🟢 Step 2/3: Agent started ✓\n"
        f"🟡 Step 3/3: Scanning in progress...\n\n"
        f"Mode: {mode_str} | Limit: {limit}\n"
        f"Use /status to check progress\n"
        f"Use /logs for detailed activity",
        parse_mode=ParseMode.MARKDOWN,
    )


# ═══════════════════════════════════════════════════════════════
# /status — Current agent state
# ═══════════════════════════════════════════════════════════════


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current agent status and last run summary."""
    if not is_authorized(update):
        return

    status = await api_get("/api/agent/status")
    stats = await api_get("/api/stats")

    if not status:
        await update.message.reply_text("🔴 Cannot reach tracker. Is it running?")
        return

    state_icons = {"idle": "⚪", "running": "🟢", "error": "🔴", "stopping": "🟡"}
    state_icon = state_icons.get(status.get("state", ""), "⚪")

    uptime = status.get("uptime_seconds", 0)
    uptime_str = f"{uptime//60}m {uptime%60}s" if uptime else "—"

    board = ""
    if stats:
        board = (
            f"\n📋 *Board:*\n"
            f"  Discovered: {stats.get('discovered', 0)}\n"
            f"  Applied: {stats.get('applied', 0)}\n"
            f"  Interviewing: {stats.get('interviewing', 0)}\n"
            f"  Total: {stats.get('total', 0)}"
        )

    await update.message.reply_text(
        f"*Agent Status*\n\n"
        f"{state_icon} State: `{status.get('state', 'unknown')}`\n"
        f"⏱ Uptime: {uptime_str}\n"
        f"🔄 Mode: {status.get('mode', '—')}\n"
        f"🛡 Dry run: {status.get('dry_run', '—')}"
        f"{board}",
        parse_mode=ParseMode.MARKDOWN,
    )


# ═══════════════════════════════════════════════════════════════
# /track_status — Kanban board summary
# ═══════════════════════════════════════════════════════════════


async def cmd_track_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show job tracking board summary."""
    if not is_authorized(update):
        return

    stats = await api_get("/api/stats")
    jobs = await api_get("/api/jobs?sort=newest")

    if not stats:
        await update.message.reply_text("🔴 Cannot reach tracker.")
        return

    # Recent jobs
    recent = ""
    if jobs:
        for j in jobs[:5]:
            score = f" ({j['match_score']:.0%})" if j.get('match_score') else ""
            stage_icon = {"discovered": "🔍", "applied": "✅", "saved": "💾", "interviewing": "📅"}.get(j.get("stage", ""), "•")
            recent += f"  {stage_icon} {j['title'][:35]} @ {j['company'][:15]}{score}\n"

    await update.message.reply_text(
        f"📊 *Job Tracker Board*\n\n"
        f"🔍 Discovered: {stats.get('discovered', 0)}\n"
        f"💾 Saved: {stats.get('saved', 0)}\n"
        f"✅ Applied: {stats.get('applied', 0)}\n"
        f"📅 Interviewing: {stats.get('interviewing', 0)}\n"
        f"🎉 Offered: {stats.get('offered', 0)}\n"
        f"❌ Rejected: {stats.get('rejected', 0)}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Total: {stats.get('total', 0)}\n\n"
        f"*Recent:*\n{recent}" if recent else "",
        parse_mode=ParseMode.MARKDOWN,
    )


# ═══════════════════════════════════════════════════════════════
# /logs — GitHub Actions-style run log
# ═══════════════════════════════════════════════════════════════


async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show last run as GitHub Actions-style step walkthrough."""
    if not is_authorized(update):
        return

    runs = await api_get("/api/agent/runs?limit=1")
    if not runs or len(runs) == 0:
        await update.message.reply_text("No runs yet. Use /run\\_agent to start one.")
        return

    run = runs[0]
    run_id = run["id"]

    # Get detailed run
    detail = await api_get(f"/api/agent/runs/{run_id}")
    if not detail:
        await update.message.reply_text("Could not fetch run details.")
        return

    # Format as GitHub Actions style
    status_icon = {"completed": "🟢", "failed": "🔴", "running": "🟡", "stopped": "⚪"}.get(detail.get("status", ""), "⚪")
    duration = detail.get("duration_seconds", "0")
    dur_str = f"{int(duration)//60}m {int(duration)%60}s" if duration else "—"

    # Parse output into steps
    output = detail.get("output_log", "")
    steps = _parse_output_to_steps(output)

    step_lines = ""
    for step in steps:
        icon = {"done": "🟢", "error": "🔴", "active": "🟡", "skipped": "⚪"}.get(step["status"], "⚪")
        time_str = f" `{step['duration']}`" if step.get("duration") else ""
        step_lines += f"  {icon} {step['name']}{time_str}\n"
        if step.get("detail"):
            step_lines += f"      ↳ {step['detail']}\n"

    # Results
    results = ""
    if detail.get("jobs_processed") and detail["jobs_processed"] != "0":
        results = (
            f"\n*Results:*\n"
            f"  Processed: {detail.get('jobs_processed', 0)}\n"
            f"  Applied: {detail.get('jobs_applied', 0)}\n"
            f"  Skipped: {detail.get('jobs_skipped', 0)}\n"
        )

    error_msg = ""
    if detail.get("error_message"):
        err = detail["error_message"][:150].replace("<", "").replace(">", "")
        error_msg = f"\n⚠️ Error: `{err}`\n"

    await update.message.reply_text(
        f"{status_icon} *Run: {detail.get('status', '?').upper()}*\n"
        f"Duration: {dur_str} | Mode: {detail.get('mode', '?')}\n"
        f"{'🛡 Dry Run' if detail.get('dry_run') == 'True' else '⚡ Live'}\n\n"
        f"*Steps:*\n{step_lines}"
        f"{results}"
        f"{error_msg}",
        parse_mode=ParseMode.MARKDOWN,
    )


def _parse_output_to_steps(output: str) -> list[dict]:
    """Parse raw output into structured steps."""
    steps = []
    lines = output.split("\n") if output else []

    step_markers = [
        ("Pipeline started", "Initialize", "done"),
        ("Browser ready", "Launch Browser", "done"),
        ("LinkedIn connected", "Session Check", "done"),
        ("session persisted", "Session Check", "done"),
        ("Session expired", "Session Check", "error"),
        ("scanning started", "Search Jobs", "done"),
        ("Custom URL", "Custom URL Search", "done"),
        ("Recommended →", "Recommended", "done"),
        ("unique jobs to evaluate", "Scan Complete", "done"),
        ("Scanning ", "Evaluate Jobs", "active"),
        ("Match score:", "Score Jobs", "done"),
        ("Worth applying", "Apply", "done"),
        ("Not worth applying", "Skip (Low Score)", "skipped"),
        ("Not Easy Apply", "Skip (External)", "skipped"),
        ("Applied successfully", "Applied!", "done"),
        ("SUMMARY", "Complete", "done"),
        ("Scan cycle complete", "Cycle Done", "done"),
        ("Error:", "Error", "error"),
    ]

    seen = set()
    for line in lines:
        for marker, name, status in step_markers:
            if marker.lower() in line.lower() and name not in seen:
                seen.add(name)
                detail = ""
                # Extract useful info
                if "→" in line:
                    detail = line.split("→")[-1].strip()[:60]
                elif "Match score:" in line:
                    detail = line.split("Match score:")[-1].strip()[:30]
                elif "unique jobs" in line.lower():
                    detail = line.strip()[-30:]

                steps.append({"name": name, "status": status, "detail": detail, "duration": ""})
                break

    return steps


# ═══════════════════════════════════════════════════════════════
# /schedule — Show scheduler config
# ═══════════════════════════════════════════════════════════════


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current scheduler configuration."""
    if not is_authorized(update):
        return

    await update.message.reply_text(
        f"⏰ *Scheduler Config*\n\n"
        f"Interval: Every 60 minutes\n"
        f"Active hours: 9:00 — 22:00\n"
        f"Status: Run `python -m linkedin\\_agent daemon` to start\n\n"
        f"*Commands:*\n"
        f"`python -m linkedin_agent daemon --dry-run` — scheduled dry runs\n"
        f"`python -m linkedin_agent daemon` — scheduled live runs",
        parse_mode=ParseMode.MARKDOWN,
    )


# ═══════════════════════════════════════════════════════════════
# /help — Command list
# ═══════════════════════════════════════════════════════════════


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available commands."""
    if not is_authorized(update):
        return

    await update.message.reply_text(
        "🤖 *ApplyPilot Bot Commands*\n\n"
        "/ping — Check if machine is online\n"
        "/run\\_agent `<limit>` — Start a scan (default: 10 jobs)\n"
        "/run\\_agent `10 --apply` — Scan AND apply\n"
        "/status — Current agent state\n"
        "/track\\_status — Job board summary\n"
        "/logs — Last run (GitHub-style steps)\n"
        "/schedule — Scheduler config\n"
        "/help — This message\n\n"
        "_Powered by Rahul_",
        parse_mode=ParseMode.MARKDOWN,
    )


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════


def main():
    """Start the Telegram bot."""
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set. Add it to .env or Settings.")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    logger.info("Starting ApplyPilot Telegram bot...")

    app = Application.builder().token(BOT_TOKEN).build()

    # Register commands
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("run_agent", cmd_run_agent))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("track_status", cmd_track_status))
    app.add_handler(CommandHandler("logs", cmd_logs))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))

    # Set bot commands menu
    async def set_commands(app):
        await app.bot.set_my_commands([
            BotCommand("run_agent", "Start a job scan"),
            BotCommand("status", "Agent status"),
            BotCommand("track_status", "Job board summary"),
            BotCommand("logs", "Last run steps"),
            BotCommand("ping", "Check machine status"),
            BotCommand("schedule", "Scheduler config"),
            BotCommand("help", "Command list"),
        ])

    app.post_init = set_commands

    logger.info("Bot ready. Listening for commands...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

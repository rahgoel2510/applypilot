#!/usr/bin/env python3
"""Telegram Bot Integration Test.

Run this script to verify your Telegram bot is configured correctly
and can send messages. Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
in your .env file.

Usage:
    python tests/test_telegram_integration.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("TELEGRAM_BOT_TOKEN") or not os.environ.get("TELEGRAM_CHAT_ID"),
    reason="TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID not set — skipping integration test",
)
@pytest.mark.asyncio
async def test_telegram():
    """Run through all Telegram notification types."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    # This guard is redundant with the skipif marker but kept for standalone usage
    assert bot_token and chat_id, "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set"

    print(f"📡 Connecting to Telegram...")
    print(f"   Bot token: {bot_token[:8]}****")
    print(f"   Chat ID:   {chat_id}")
    print()

    from linkedin_agent.telegram_bot import TelegramNotifier

    notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)

    # Test 1: Basic notification
    print("1️⃣  Sending basic notification...")
    try:
        await notifier.send_notification("🧪 Test 1/4: Basic notification from LinkedIn Agent")
        print("   ✅ Basic notification sent!")
    except Exception as exc:
        print(f"   ❌ Failed: {exc}")
        return

    await asyncio.sleep(1)

    # Test 2: Job submitted notification
    print("2️⃣  Sending job-submitted notification...")
    try:
        await notifier.send_notification(
            "✅ *Applied*: Senior Backend Engineer @ TechCorp\n"
            "📍 Bangalore | Match: 85%"
        )
        print("   ✅ Job notification sent!")
    except Exception as exc:
        print(f"   ❌ Failed: {exc}")

    await asyncio.sleep(1)

    # Test 3: Tally report
    print("3️⃣  Sending tally report...")
    try:
        tally = {
            "submitted": 3,
            "paused": 1,
            "skipped_threshold": 5,
            "skipped_external": 2,
        }
        await notifier.send_tally_report(tally)
        print("   ✅ Tally report sent!")
    except Exception as exc:
        print(f"   ❌ Failed: {exc}")

    await asyncio.sleep(1)

    # Test 4: InMail draft preview
    print("4️⃣  Sending InMail draft preview...")
    try:
        draft = (
            "Hi Priya,\n\n"
            "I came across the Senior Backend Engineer role at TechCorp and "
            "it immediately stood out. My 5+ years building distributed systems "
            "in Python aligns well with what you're looking for.\n\n"
            "Would you be open to a brief chat about the role?\n\n"
            "Best,\nRahul"
        )
        await notifier.send_inmail_draft(
            job_title="Senior Backend Engineer",
            company="TechCorp",
            recruiter="Priya Sharma",
            draft=draft,
        )
        print("   ✅ InMail draft sent!")
    except Exception as exc:
        print(f"   ❌ Failed: {exc}")

    print()
    print("=" * 50)
    print("✅ All Telegram tests complete!")
    print("   Check your Telegram chat to verify messages arrived.")


if __name__ == "__main__":
    asyncio.run(test_telegram())

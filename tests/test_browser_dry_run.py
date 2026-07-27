#!/usr/bin/env python3
"""Browser Dry-Run Test.

Opens a visible browser, logs into LinkedIn (using saved session or credentials),
navigates to the job collection, reads job cards + match scores, and prints
results WITHOUT applying to anything.

This verifies:
- Browser automation works
- LinkedIn login/session persistence works
- Job card scraping works
- Match score reading works

Usage:
    python tests/test_browser_dry_run.py [--limit 5] [--collection "Recommended"]

Requirements:
    - LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env (for first login)
    - playwright install chromium (run once)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


async def run_dry_run(limit: int = 5, collection: str = "Recommended"):
    """Execute a browser dry-run scan."""
    from linkedin_agent.config import get_config
    from linkedin_agent.browser import LinkedInBrowser
    from linkedin_agent.matcher import JobMatcher

    print("=" * 60)
    print("🧪 LinkedIn Agent — Browser Dry Run")
    print("=" * 60)
    print(f"   Collection: {collection}")
    print(f"   Limit:      {limit} jobs")
    print(f"   Mode:       READ-ONLY (no applications)")
    print()

    try:
        config = get_config(validate=True)
    except Exception as exc:
        print(f"❌ Config error: {exc}")
        print("   Make sure .env has all required variables.")
        sys.exit(1)

    matcher = JobMatcher(threshold=config.job_search.match_threshold)
    browser = LinkedInBrowser()

    print("🌐 Launching browser (headed mode)...")
    try:
        # Force headed mode for dry run
        await browser.launch(headless=False)
        print("   ✅ Browser launched")
    except Exception as exc:
        print(f"   ❌ Browser launch failed: {exc}")
        sys.exit(1)

    print("\n🔐 Checking LinkedIn session...")
    try:
        await browser.login(email=config.linkedin_email, password=config.linkedin_password)
        print("   ✅ Logged in")
    except Exception as exc:
        # Check if we actually ended up on feed (challenge completed during timeout)
        if browser.page and "/feed" in browser.page.url:
            print("   ✅ Logged in (passed security challenge)")
        else:
            print(f"   ⚠️  Auto-login needs help: {str(exc)[:60]}")
            print("   Please log in manually in the browser window.")
            print("   ⏳ Waiting 60s for you to log in...")
            await asyncio.sleep(60)
            # Verify after manual login
            if "/feed" not in browser.page.url:
                print("   ❌ Still not logged in. Exiting.")
                await browser.close()
                sys.exit(1)
            print("   ✅ Manual login successful!")

    print(f"\n📂 Navigating to '{collection}' collection...")
    try:
        await browser.navigate_to_jobs(collection=collection)
        print("   ✅ Navigation successful")
    except Exception as exc:
        print(f"   ❌ Navigation failed: {exc}")
        print("   You may need to log in manually on first run.")
        # Keep browser open for manual login
        print("\n⏳ Keeping browser open for 60s for manual login...")
        await asyncio.sleep(60)
        await browser.close()
        sys.exit(1)

    print(f"\n🔍 Reading job listings (limit: {limit})...")
    try:
        jobs = await browser.get_job_listings(max_count=limit)
        print(f"   ✅ Found {len(jobs)} job(s)")
    except Exception as exc:
        print(f"   ❌ Failed to read job listings: {exc}")
        await browser.close()
        sys.exit(1)

    # Display results
    print("\n" + "=" * 60)
    print("📋 JOB LISTINGS (Dry Run — No Applications)")
    print("=" * 60)

    submitted_count = 0
    skipped_count = 0

    for i, job in enumerate(jobs, 1):
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        location = job.get("location", "Unknown")
        is_external = job.get("is_external", False)
        match_score = job.get("match_score")
        matched = job.get("matched_qualifications", "?")
        required = job.get("required_qualifications", "?")

        # Determine what would happen
        if is_external:
            decision = "🚫 SKIP (external)"
            skipped_count += 1
        elif matcher.is_duplicate(company, title):
            decision = "🔁 SKIP (duplicate)"
            skipped_count += 1
        elif match_score is not None and not matcher.meets_threshold(match_score):
            decision = f"⚠️  SKIP (score {match_score:.0%} < {config.job_search.match_threshold:.0%})"
            skipped_count += 1
        elif match_score is not None and matcher.meets_threshold(match_score):
            decision = f"✅ WOULD APPLY (score {match_score:.0%})"
            submitted_count += 1
        else:
            decision = "❓ UNKNOWN (no score available)"
            skipped_count += 1

        print(f"\n  [{i}] {title}")
        print(f"      Company:  {company}")
        print(f"      Location: {location}")
        if match_score is not None:
            print(f"      Match:    {matched}/{required} ({match_score:.0%})")
        print(f"      Decision: {decision}")

    # Summary
    print("\n" + "=" * 60)
    print("📊 DRY RUN SUMMARY")
    print("=" * 60)
    print(f"   Total scanned:    {len(jobs)}")
    print(f"   Would apply:      {submitted_count}")
    print(f"   Would skip:       {skipped_count}")
    print(f"   Threshold:        {config.job_search.match_threshold:.0%}")
    print()

    # Keep browser open briefly for inspection
    print("⏳ Browser stays open for 10s for inspection...")
    await asyncio.sleep(10)

    await browser.close()
    print("✅ Browser closed. Dry run complete!")


def main():
    parser = argparse.ArgumentParser(description="Browser dry-run test")
    parser.add_argument(
        "--limit", type=int, default=5, help="Number of jobs to scan"
    )
    parser.add_argument(
        "--collection", default="Recommended", help="Job collection name"
    )
    args = parser.parse_args()

    asyncio.run(run_dry_run(limit=args.limit, collection=args.collection))


if __name__ == "__main__":
    main()

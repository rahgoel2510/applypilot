#!/usr/bin/env python3
"""Live Pipeline Debugger — Runs the FULL agent pipeline step-by-step with y/n confirmation.

Opens a VISIBLE browser. Shows real-time updates in terminal AND pushes events
to the dashboard (http://localhost:5173) so you can watch both.

Every major action asks for your approval before proceeding.
"""
import asyncio
import os
import re
import sys
import urllib.parse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright

BROWSER_DATA = Path.home() / "Library/Application Support/linkedin_agent/browser_data"
LINKEDIN_JOBS = "https://www.linkedin.com/jobs/"
LINKEDIN_FEED = "https://www.linkedin.com/feed/"

# Load config
from dotenv import load_dotenv
load_dotenv()


class Colors:
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def ask(prompt):
    """Ask user y/n with colored prompt."""
    while True:
        resp = input(f"\n  {Colors.YELLOW}👉 {prompt} (y/n):{Colors.RESET} ").strip().lower()
        if resp in ("y", "yes"):
            return True
        if resp in ("n", "no"):
            return False


def step(num, title):
    """Print a step header."""
    print(f"\n  {Colors.CYAN}{'━' * 55}")
    print(f"  ┃ STEP {num}: {title}")
    print(f"  {'━' * 55}{Colors.RESET}")


def result(icon, msg, data=None):
    """Print a result."""
    print(f"  {icon} {Colors.BOLD}{msg}{Colors.RESET}")
    if data:
        if isinstance(data, list):
            for i, item in enumerate(data[:15], 1):
                if isinstance(item, dict):
                    score_str = f" ({item['score']}%)" if item.get('score') else ""
                    decision_str = f" → {item['decision']}" if item.get('decision') else ""
                    print(f"    {Colors.DIM}[{i:2d}]{Colors.RESET} {item.get('title', '?')[:45]} @ {item.get('company', '?')[:20]}{score_str}{decision_str}")
                else:
                    print(f"    {Colors.DIM}[{i:2d}]{Colors.RESET} {item}")
            if len(data) > 15:
                print(f"    {Colors.DIM}... and {len(data) - 15} more{Colors.RESET}")
        elif isinstance(data, dict):
            for k, v in data.items():
                print(f"    {Colors.DIM}{k}:{Colors.RESET} {v}")


def push_to_dashboard(event_type, title="", company="", message="", score=None):
    """Push event to dashboard WebSocket (non-blocking)."""
    try:
        import requests
        requests.post("http://localhost:8000/api/webhook", json={
            "event": event_type,
            "title": title,
            "company": company,
            "message": message,
            "match_score": score,
        }, timeout=1)
    except Exception:
        pass


async def push_screenshot(page, name="pipeline_step"):
    """Capture browser screenshot and push to dashboard."""
    try:
        import base64, requests
        screenshot_bytes = await page.screenshot(type="png")
        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        requests.post("http://localhost:8000/api/agent/screenshot", json={
            "image": b64,
            "name": name,
        }, timeout=3)
    except Exception:
        pass
        pass


async def extract_jobs(page, max_jobs=50):
    """Extract job cards from current page with full scrolling + pagination."""
    all_jobs = []
    seen_ids = set()
    page_num = 1

    while len(all_jobs) < max_jobs:
        # Scroll to load all cards on this page
        prev_count = 0
        for i in range(30):
            await page.evaluate('() => { const l = document.querySelector(".scaffold-layout__list") || document.querySelector("main"); if(l) l.scrollTop += 400; else window.scrollBy(0,400); }')
            await asyncio.sleep(0.5)
            links = await page.query_selector_all('a[href*="/jobs/view/"]')
            if len(links) > prev_count:
                prev_count = len(links)
            elif i > 10:
                await asyncio.sleep(1.0)
                final = await page.query_selector_all('a[href*="/jobs/view/"]')
                if len(final) <= prev_count:
                    break
                prev_count = len(final)
        await asyncio.sleep(0.5)

        # Extract jobs from this page
        links = await page.query_selector_all('a[href*="/jobs/view/"]')
        new_on_page = 0
        for link in links:
            if len(all_jobs) >= max_jobs:
                break
            href = await link.get_attribute("href") or ""
            m = re.search(r"/jobs/view/(\d+)", href)
            if not m:
                continue
            job_id = m.group(1)
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            title = (await link.inner_text()).strip().split("\n")[0].strip()[:60]
            company = ""
            location = ""
            try:
                card = await link.evaluate_handle("el => el.closest('li') || el.parentElement.parentElement.parentElement")
                card_el = card.as_element()
                if card_el:
                    card_text = await card_el.inner_text()
                    lines = [l.strip() for l in card_text.split("\n") if l.strip() and len(l.strip()) > 1]
                    remaining = [l for l in lines if l != title and title not in l
                                and "verification" not in l.lower() and "easy apply" not in l.lower()
                                and "actively hiring" not in l.lower() and "promoted" not in l.lower()]
                    if remaining:
                        company = remaining[0][:40]
                    if len(remaining) >= 2:
                        location = remaining[1][:40]
            except Exception:
                pass

            all_jobs.append({"job_id": job_id, "title": title, "company": company, "location": location})
            new_on_page += 1

        print(f"    {Colors.DIM}Page {page_num}: {new_on_page} jobs (total: {len(all_jobs)}){Colors.RESET}")

        if new_on_page == 0 or len(all_jobs) >= max_jobs:
            break

        # Try pagination
        try:
            next_btn = page.locator("button[aria-label='View next page']").first
            if await next_btn.is_visible(timeout=2000):
                await next_btn.click()
                await asyncio.sleep(3)
                await page.evaluate('() => { const l = document.querySelector(".scaffold-layout__list"); if(l) l.scrollTop = 0; }')
                await asyncio.sleep(1)
                page_num += 1
            else:
                break
        except Exception:
            break

    return all_jobs


async def score_job(page, job, config):
    """Open a job and get its score."""
    await page.goto(f"https://www.linkedin.com/jobs/view/{job['job_id']}/", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)

    # Check Easy Apply
    easy_apply = await page.query_selector('button[aria-label*="Easy Apply"], button:has-text("Easy Apply")')
    job["easy_apply"] = easy_apply is not None

    # Check external
    if not job["easy_apply"]:
        ext_btn = await page.query_selector('button[aria-label*="Apply"], a[href*="apply"]')
        job["external"] = ext_btn is not None
    else:
        job["external"] = False

    # Try LinkedIn AI score (Premium only)
    try:
        match_el = page.locator("text=Show match details").first
        if await match_el.is_visible(timeout=2000):
            await match_el.click()
            await asyncio.sleep(5)
            overlay = await page.query_selector("[class*='overlay'], [class*='coach'], [role='dialog']")
            if overlay:
                text = await overlay.inner_text()
                m = re.search(r"(\d+)\s+of\s+(?:the\s+)?(\d+)", text)
                if m:
                    matched, total = int(m.group(1)), int(m.group(2))
                    job["score"] = round(matched / total * 100)
                    job["score_method"] = "linkedin_ai"
                    return
    except Exception:
        pass

    # Fallback: keyword scoring
    keywords = config.get("keywords", [])
    title_lower = job["title"].lower()
    company_lower = job["company"].lower()
    matches = sum(1 for kw in keywords if kw.lower() in title_lower or kw.lower() in company_lower)
    job["score"] = min(100, round((matches / max(len(keywords), 1)) * 100 + 30))  # Base 30 + keyword match
    job["score_method"] = "keyword"


async def run_live():
    print()
    print(f"  {Colors.MAGENTA}{'═' * 55}")
    print(f"  ║  🔬 APPLYPILOT — LIVE PIPELINE DEBUGGER")
    print(f"  ║  Real-time • Visible Browser • Dashboard Sync")
    print(f"  {'═' * 55}{Colors.RESET}")
    print()
    print(f"  {Colors.DIM}Dashboard: http://localhost:5173 (watch Pipeline tab){Colors.RESET}")
    print()

    # Load config
    from linkedin_agent.config import get_config
    try:
        config = get_config()
        keywords = config.job_search.keywords
        locations = config.job_search.locations
        threshold = config.job_search.match_threshold
        max_postings = config.job_search.max_postings_per_run
    except Exception:
        keywords = ["Engineering Manager", "Technical Program Manager"]
        locations = ["India", "Bangalore"]
        threshold = 0.8
        max_postings = 50

    print(f"  Config loaded:")
    print(f"    Keywords:  {keywords}")
    print(f"    Locations: {locations}")
    print(f"    Threshold: {threshold:.0%}")
    print(f"    Max jobs:  {max_postings}")

    # ─── STEP 1: Launch ─────────────────────────────────────────
    step(1, "Launch Browser")
    if not ask("Open visible Chrome with your LinkedIn session?"):
        return

    push_to_dashboard("info", message="Pipeline debugger starting...")

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA),
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        result("🌐", "Browser launched")

        # ─── STEP 2: Session Check ─────────────────────────────
        step(2, "Verify LinkedIn Session")
        if not ask("Check if your LinkedIn session is valid?"):
            await ctx.close()
            return

        await page.goto(LINKEDIN_FEED, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        if "/login" in page.url or "/authwall" in page.url:
            result("❌", "Session EXPIRED", {"URL": page.url[:60]})
            print(f"\n  {Colors.RED}Run 'python3 login.py' first to log in.{Colors.RESET}")
            await ctx.close()
            return

        result("✅", "LinkedIn session valid", {"URL": page.url[:50]})
        push_to_dashboard("info", message="LinkedIn session verified ✓")
        await push_screenshot(page, "01_feed_verified")

        # Verify jobs access
        await page.goto(LINKEDIN_JOBS, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)
        if "/login" in page.url or "/authwall" in page.url:
            result("❌", "Jobs section blocked — session partially expired")
            await ctx.close()
            return
        result("✅", "Jobs section accessible")
        await push_screenshot(page, "02_jobs_accessible")

        # ─── STEP 3: Discovery ──────────────────────────────────
        step(3, "Discover Jobs")
        all_jobs = []

        # 3a: Recommended
        if ask("Check Recommended jobs?"):
            push_to_dashboard("info", message="Checking Recommended jobs...")
            await page.goto(f"{LINKEDIN_JOBS}collections/recommended/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            if "/login" not in page.url and "/authwall" not in page.url:
                print(f"    {Colors.DIM}Extracting recommended jobs...{Colors.RESET}")
                rec_jobs = await extract_jobs(page, max_jobs=25)
                all_jobs.extend(rec_jobs)
                result("📋", f"Recommended: {len(rec_jobs)} jobs found", rec_jobs[:5])
                push_to_dashboard("info", message=f"Recommended: {len(rec_jobs)} jobs")
                await push_screenshot(page, "03_recommended")
            else:
                result("⚠️", "Recommended page not accessible (normal)")

        # 3b: Keyword searches
        for keyword in keywords:
            for location in locations:
                if len(all_jobs) >= max_postings:
                    break
                if not ask(f"Search '{keyword}' in '{location}'?"):
                    continue

                push_to_dashboard("info", message=f"Searching: {keyword} in {location}...")
                params = {"keywords": keyword, "location": location, "f_TPR": "r86400"}
                url = f"{LINKEDIN_JOBS}search/?{urllib.parse.urlencode(params)}"

                await page.goto(url, wait_until="domcontentloaded", timeout=90000)
                await asyncio.sleep(4)

                if "/login" in page.url or "/authwall" in page.url:
                    result("❌", f"Search blocked for '{keyword}' in {location}")
                    continue

                print(f"    {Colors.DIM}Extracting jobs (with pagination)...{Colors.RESET}")
                remaining = max_postings - len(all_jobs)
                search_jobs = await extract_jobs(page, max_jobs=min(remaining, 25))

                # Deduplicate
                seen_ids = {j["job_id"] for j in all_jobs}
                new_jobs = [j for j in search_jobs if j["job_id"] not in seen_ids]
                all_jobs.extend(new_jobs)

                result("🔍", f"'{keyword}' in {location}: {len(new_jobs)} new jobs", new_jobs[:5])
                push_to_dashboard("info", message=f"{keyword} in {location}: {len(new_jobs)} jobs")
                await push_screenshot(page, f"04_search_{keyword[:10]}_{location[:10]}")

        print(f"\n  {Colors.GREEN}{'─' * 55}")
        print(f"  📊 TOTAL DISCOVERED: {len(all_jobs)} unique jobs")
        print(f"  {'─' * 55}{Colors.RESET}")

        if not all_jobs:
            result("⚠️", "No jobs found — check your keywords/locations")
            await ctx.close()
            return

        # ─── STEP 4: Evaluate ───────────────────────────────────
        step(4, "Evaluate & Score Jobs")
        if not ask(f"Score all {len(all_jobs)} jobs? (opens each one to check)"):
            # Just show raw list
            result("📋", "Jobs discovered (unscored)", all_jobs[:20])
            input(f"\n  {Colors.DIM}Press ENTER to close...{Colors.RESET}")
            await ctx.close()
            return

        qualified = []
        skipped = []
        external = []

        for idx, job in enumerate(all_jobs, 1):
            print(f"\n  {Colors.CYAN}🎯 [{idx}/{len(all_jobs)}]{Colors.RESET} {job['title']} @ {job['company']}")
            push_to_dashboard("discovered", title=job["title"], company=job["company"])

            if not ask(f"Open and score this job?"):
                print(f"    {Colors.DIM}Skipped by user{Colors.RESET}")
                continue

            await score_job(page, job, {"keywords": keywords})
            await push_screenshot(page, f"05_job_{idx}_{job['job_id']}")
            score_pct = job.get("score", 0)
            method = job.get("score_method", "?")
            is_easy = job.get("easy_apply", False)
            is_ext = job.get("external", False)

            # Show result
            score_color = Colors.GREEN if score_pct >= threshold * 100 else Colors.YELLOW if score_pct >= 50 else Colors.RED
            print(f"    Score: {score_color}{score_pct}%{Colors.RESET} ({method})")
            print(f"    Easy Apply: {'✅' if is_easy else '❌'}")
            print(f"    External: {'🔗 Yes' if is_ext else 'No'}")

            # Decision
            if is_ext:
                job["decision"] = "external"
                external.append(job)
                print(f"    {Colors.MAGENTA}→ External apply (link saved){Colors.RESET}")
                push_to_dashboard("discovered", title=job["title"], company=job["company"], score=score_pct/100)
            elif score_pct >= threshold * 100:
                job["decision"] = "qualified"
                qualified.append(job)
                print(f"    {Colors.GREEN}→ ✅ QUALIFIES! Would apply in live mode.{Colors.RESET}")
                push_to_dashboard("submitted", title=job["title"], company=job["company"], score=score_pct/100)
            else:
                job["decision"] = "skipped"
                skipped.append(job)
                print(f"    {Colors.DIM}→ ❌ Below {threshold:.0%} threshold — skipped{Colors.RESET}")
                push_to_dashboard("skipped", title=job["title"], company=job["company"], score=score_pct/100)

        # ─── STEP 5: Summary ───────────────────────────────────
        step(5, "Run Summary")
        print()
        print(f"  {Colors.GREEN}{'═' * 55}")
        print(f"  ║  📊 PIPELINE RESULTS")
        print(f"  {'═' * 55}{Colors.RESET}")
        print(f"    Total discovered:  {len(all_jobs)}")
        print(f"    ✅ Qualified:       {len(qualified)}")
        print(f"    ❌ Skipped:         {len(skipped)}")
        print(f"    🔗 External:        {len(external)}")
        print()

        if qualified:
            print(f"  {Colors.GREEN}Jobs that would be applied to:{Colors.RESET}")
            for j in qualified:
                print(f"    ✅ {j['title']} @ {j['company']} ({j['score']}%)")

        if external:
            print(f"\n  {Colors.MAGENTA}External apply links:{Colors.RESET}")
            for j in external:
                print(f"    🔗 {j['title']} @ {j['company']}")
                print(f"       https://www.linkedin.com/jobs/view/{j['job_id']}/")

        print(f"\n  {Colors.GREEN}{'═' * 55}{Colors.RESET}")
        push_to_dashboard("info", message=f"Debug complete: {len(qualified)} qualified, {len(skipped)} skipped, {len(external)} external")

        input(f"\n  {Colors.DIM}Press ENTER to close the browser...{Colors.RESET} ")
        await ctx.close()


if __name__ == "__main__":
    asyncio.run(run_live())

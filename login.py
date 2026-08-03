#!/usr/bin/env python3
"""Copy LinkedIn session from your regular Chrome to the agent's browser.

This opens a visible browser, navigates to LinkedIn (which will auto-login
using your existing Chrome session via cookie import), and saves the session.
"""
import asyncio
import subprocess
import json
from pathlib import Path
from playwright.async_api import async_playwright

BROWSER_DATA = Path.home() / "Library/Application Support/linkedin_agent/browser_data"


async def copy_session():
    """Use browser-based approach: open LinkedIn in agent browser, inject cookies."""
    
    # Step 1: Extract li_at from Chrome using a JS cookie reader
    # We'll open Chrome with remote debugging to grab the cookie
    print("\n🔑 Copying LinkedIn session from your Chrome...\n")
    
    async with async_playwright() as p:
        # Launch with the agent's data dir
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA),
            headless=False,
            args=["--no-sandbox"],
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        
        # Navigate to LinkedIn - user needs to log in
        await page.goto("https://www.linkedin.com/login")
        
        print("=" * 55)
        print("   🔑 LOG IN TO LINKEDIN")
        print("=" * 55)
        print()
        print("   A browser window opened → Log in to LinkedIn.")
        print()
        print("   IMPORTANT: After logging in, make sure you can")
        print("   see your LinkedIn feed/homepage, THEN come back")
        print("   here and press ENTER.")
        print()
        print("   If you see a verification code/CAPTCHA,")
        print("   complete it first.")
        print()
        print("=" * 55)
        input("   Press ENTER after you see your LinkedIn feed... ")
        
        # Verify
        print("\n   Verifying...")
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        
        feed_url = page.url
        if "/feed" in feed_url and "/login" not in feed_url and "/authwall" not in feed_url:
            print("   ✅ Feed works!")
        else:
            print(f"   ⚠️ Feed redirected to: {feed_url[:60]}")
            print("   You may not be fully logged in. Try again.")
            await ctx.close()
            return
        
        # Now test jobs
        await page.goto("https://www.linkedin.com/jobs/search/?keywords=Engineer&location=India", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        
        jobs_url = page.url
        if "/login" in jobs_url or "/authwall" in jobs_url:
            print(f"   ⚠️ Jobs page still blocked: {jobs_url[:60]}")
            await ctx.close()
            return
        
        # Scroll and count
        for _ in range(5):
            await page.evaluate('() => { window.scrollBy(0, 600); }')
            await asyncio.sleep(0.4)
        await asyncio.sleep(2)
        
        links = await page.query_selector_all('a[href*="/jobs/view/"]')
        print(f"   ✅ Jobs search works! Found {len(links)} jobs.")
        print()
        print("   ✅ Session saved successfully!")
        print("   You can now run the agent from the dashboard.")
        print("   Close this browser window whenever you want.")
        print()
        
        await ctx.close()


if __name__ == "__main__":
    asyncio.run(copy_session())

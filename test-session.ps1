#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════
# ApplyPilot — Test LinkedIn Session (Windows)
# ═══════════════════════════════════════════════════════════
# Checks if your LinkedIn session is valid WITHOUT running a full scan.
# If no session exists, opens a browser for you to log in.
# ═══════════════════════════════════════════════════════════

Write-Host ""
Write-Host "  ApplyPilot — LinkedIn Session Test" -ForegroundColor Cyan
Write-Host "  ====================================" -ForegroundColor Cyan
Write-Host ""

# Check if session directory exists
$sessionPath = "$env:LOCALAPPDATA\linkedin_agent\linkedin_agent\browser_data\Default"
$altPath = "$env:LOCALAPPDATA\linkedin_agent\browser_data\Default"

$foundPath = $null
if (Test-Path $sessionPath) { $foundPath = $sessionPath }
elseif (Test-Path $altPath) { $foundPath = $altPath }

if ($foundPath) {
    Write-Host "  [1] Session files found at:" -ForegroundColor Green
    Write-Host "      $foundPath" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "  [1] No session found." -ForegroundColor Red
    Write-Host "      Will open browser for you to log in." -ForegroundColor Yellow
    Write-Host ""
}

# Test the session by launching headless browser and checking /feed
Write-Host "  [2] Testing session against LinkedIn..." -ForegroundColor Yellow

$testScript = @"
import asyncio, sys, time
from linkedin_agent.browser import LinkedInBrowser

async def test():
    b = LinkedInBrowser()
    await b.launch(headless=True)
    t0 = time.time()
    page = b.page
    try:
        await page.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded', timeout=15000)
        await asyncio.sleep(3)
        url = page.url
        elapsed = time.time() - t0
        if '/feed' in url and '/login' not in url:
            print(f'VALID|{elapsed:.1f}')
        else:
            print(f'EXPIRED|{elapsed:.1f}|{url}')
    except Exception as e:
        print(f'ERROR|{e}')
    finally:
        await b.close()

asyncio.run(test())
"@

$result = python -c $testScript 2>$null
$parts = $result -split '\|'

Write-Host ""
if ($parts[0] -eq 'VALID') {
    Write-Host "  ✅ SESSION IS VALID!" -ForegroundColor Green
    Write-Host "     LinkedIn responded in $($parts[1])s" -ForegroundColor Gray
    Write-Host "     Your agent is ready to scan." -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Next: python -m linkedin_agent run --dry-run --limit 10" -ForegroundColor Cyan
}
elseif ($parts[0] -eq 'EXPIRED') {
    Write-Host "  ❌ SESSION EXPIRED" -ForegroundColor Red
    Write-Host "     LinkedIn redirected to: $($parts[2])" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Opening browser for login..." -ForegroundColor Yellow
    Write-Host "  Log in manually, then close the browser." -ForegroundColor Yellow
    Write-Host ""
    python -c "import asyncio;from linkedin_agent.browser import LinkedInBrowser;b=LinkedInBrowser();asyncio.run(b.launch(headless=False));import time;print('Waiting 60s for login...');time.sleep(60);asyncio.run(b.close());print('Session saved.')"
    Write-Host ""
    Write-Host "  Session saved. Run this script again to verify." -ForegroundColor Green
}
elseif ($parts[0] -eq 'ERROR') {
    Write-Host "  ❌ ERROR: $($parts[1])" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Make sure Playwright is installed:" -ForegroundColor Yellow
    Write-Host "     pip install playwright" -ForegroundColor Gray
    Write-Host "     playwright install chromium" -ForegroundColor Gray
}
else {
    Write-Host "  ⚠️  Unexpected result: $result" -ForegroundColor Yellow
    Write-Host "  Opening browser for fresh login..." -ForegroundColor Yellow
    python tests/test_browser_dry_run.py --limit 1
}

Write-Host ""

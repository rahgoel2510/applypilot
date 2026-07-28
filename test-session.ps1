#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════
# ApplyPilot — Test LinkedIn Session (Windows)
# ═══════════════════════════════════════════════════════════

Write-Host ""
Write-Host "  ApplyPilot - LinkedIn Session Test" -ForegroundColor Cyan
Write-Host "  ====================================" -ForegroundColor Cyan
Write-Host ""

# Check if session directory exists
$sessionPath = "$env:LOCALAPPDATA\linkedin_agent\linkedin_agent\browser_data\Default"
$altPath = "$env:LOCALAPPDATA\linkedin_agent\browser_data\Default"

$foundPath = $null
if (Test-Path $sessionPath) { $foundPath = $sessionPath }
elseif (Test-Path $altPath) { $foundPath = $altPath }

if ($foundPath) {
    Write-Host "  [1] Session files found" -ForegroundColor Green
    Write-Host "      $foundPath" -ForegroundColor Gray
} else {
    Write-Host "  [1] No session found" -ForegroundColor Red
    Write-Host "      Will open browser for you to log in." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Running browser login..." -ForegroundColor Yellow
    python tests/test_browser_dry_run.py --limit 1
    Write-Host ""
    Write-Host "  Done. Run this script again to verify." -ForegroundColor Green
    exit
}

Write-Host ""
Write-Host "  [2] Testing session against LinkedIn..." -ForegroundColor Yellow

# Write python test to a temp file (avoids PowerShell parsing issues)
$tempFile = [System.IO.Path]::GetTempFileName() + ".py"
Set-Content -Path $tempFile -Value @'
import asyncio, time, sys
sys.path.insert(0, '.')
from linkedin_agent.browser import LinkedInBrowser

async def test():
    b = LinkedInBrowser()
    await b.launch(headless=True)
    t0 = time.time()
    page = b.page
    try:
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(3)
        url = page.url
        elapsed = time.time() - t0
        if "/feed" in url and "/login" not in url:
            print(f"VALID {elapsed:.1f}s")
        else:
            print(f"EXPIRED {elapsed:.1f}s")
    except Exception as e:
        print(f"ERROR {e}")
    finally:
        await b.close()

asyncio.run(test())
'@

$result = python $tempFile 2>$null
Remove-Item $tempFile -ErrorAction SilentlyContinue

Write-Host ""
if ($result -match "^VALID") {
    $time = ($result -split " ")[1]
    Write-Host "  ====================================" -ForegroundColor Green
    Write-Host "  SESSION IS VALID!" -ForegroundColor Green
    Write-Host "  LinkedIn responded in $time" -ForegroundColor Gray
    Write-Host "  Your agent is ready to scan." -ForegroundColor Gray
    Write-Host "  ====================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Next:" -ForegroundColor Cyan
    Write-Host "    python -m linkedin_agent run --dry-run --limit 10" -ForegroundColor White
}
elseif ($result -match "^EXPIRED") {
    Write-Host "  ====================================" -ForegroundColor Red
    Write-Host "  SESSION EXPIRED" -ForegroundColor Red
    Write-Host "  ====================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Opening browser for login..." -ForegroundColor Yellow
    Write-Host "  Log in to LinkedIn, then wait for the script to finish." -ForegroundColor Yellow
    Write-Host ""
    python tests/test_browser_dry_run.py --limit 1
    Write-Host ""
    Write-Host "  Session saved. Run this script again to verify." -ForegroundColor Green
}
else {
    Write-Host "  ERROR: $result" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Make sure Playwright is installed:" -ForegroundColor Yellow
    Write-Host "    pip install playwright" -ForegroundColor Gray
    Write-Host "    playwright install chromium" -ForegroundColor Gray
}

Write-Host ""

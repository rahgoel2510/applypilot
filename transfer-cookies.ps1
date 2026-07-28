#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════
# ApplyPilot — Transfer LinkedIn Cookies to Docker
# ═══════════════════════════════════════════════════════════
# Exports cookies from your local Playwright session and
# injects them into Docker's browser context.
# This bypasses the OS/version mismatch issue.
# ═══════════════════════════════════════════════════════════

$containerName = (docker ps --format "{{.Names}}" 2>$null | Select-String "applypilot").Matches.Value

Write-Host ""
Write-Host "  ApplyPilot - Cookie Transfer" -ForegroundColor Cyan
Write-Host "  ==============================" -ForegroundColor Cyan
Write-Host ""

if (-not $containerName) {
    Write-Host "  Container not running." -ForegroundColor Red
    exit 1
}

# Step 1: Export cookies from local Playwright session
Write-Host "  [1] Exporting cookies from local session..." -ForegroundColor Yellow

$exportPy = 'import asyncio, json' + "`n"
$exportPy += 'from playwright.async_api import async_playwright' + "`n"
$exportPy += 'from platformdirs import user_data_dir' + "`n"
$exportPy += 'from pathlib import Path' + "`n"
$exportPy += 'async def export():' + "`n"
$exportPy += '    data_dir = Path(user_data_dir("linkedin_agent", "linkedin_agent")) / "browser_data"' + "`n"
$exportPy += '    pw = await async_playwright().start()' + "`n"
$exportPy += '    ctx = await pw.chromium.launch_persistent_context(str(data_dir), headless=True)' + "`n"
$exportPy += '    cookies = await ctx.cookies()' + "`n"
$exportPy += '    linkedin_cookies = [c for c in cookies if "linkedin" in c.get("domain", "")]' + "`n"
$exportPy += '    with open("linkedin_cookies.json", "w") as f:' + "`n"
$exportPy += '        json.dump(linkedin_cookies, f)' + "`n"
$exportPy += '    print(f"EXPORTED {len(linkedin_cookies)} cookies")' + "`n"
$exportPy += '    await ctx.close()' + "`n"
$exportPy += '    await pw.stop()' + "`n"
$exportPy += 'asyncio.run(export())' + "`n"

$tmp = Join-Path $env:TEMP "ap_export.py"
Set-Content -Path $tmp -Value $exportPy -NoNewline
$result = python $tmp 2>$null
Remove-Item $tmp -ErrorAction SilentlyContinue

if (-not ($result -match "EXPORTED")) {
    Write-Host "  Failed to export cookies. Is local session valid?" -ForegroundColor Red
    Write-Host "  Run: test-session.ps1" -ForegroundColor Yellow
    exit 1
}
Write-Host "  $result" -ForegroundColor Green

# Step 2: Copy cookies file to Docker
Write-Host "  [2] Copying cookies to container..." -ForegroundColor Yellow
docker cp "linkedin_cookies.json" "${containerName}:/tmp/linkedin_cookies.json" 2>$null

# Step 3: Import cookies inside Docker
Write-Host "  [3] Importing cookies inside Docker..." -ForegroundColor Yellow

$importPy = 'import asyncio, json' + "`n"
$importPy += 'from linkedin_agent.browser import LinkedInBrowser' + "`n"
$importPy += 'async def imp():' + "`n"
$importPy += '    with open("/tmp/linkedin_cookies.json") as f:' + "`n"
$importPy += '        cookies = json.load(f)' + "`n"
$importPy += '    b = LinkedInBrowser()' + "`n"
$importPy += '    await b.launch(headless=True)' + "`n"
$importPy += '    ctx = b._context' + "`n"
$importPy += '    await ctx.add_cookies(cookies)' + "`n"
$importPy += '    page = b.page' + "`n"
$importPy += '    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")' + "`n"
$importPy += '    await asyncio.sleep(5)' + "`n"
$importPy += '    if "/feed" in page.url and "/login" not in page.url:' + "`n"
$importPy += '        print("SESSION_VALID")' + "`n"
$importPy += '        # Save by visiting a page (persistent context auto-saves)' + "`n"
$importPy += '        await page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")' + "`n"
$importPy += '        await asyncio.sleep(2)' + "`n"
$importPy += '    else:' + "`n"
$importPy += '        print("SESSION_INVALID")' + "`n"
$importPy += '    await b.close()' + "`n"
$importPy += 'asyncio.run(imp())' + "`n"

$tmp = Join-Path $env:TEMP "ap_import.py"
Set-Content -Path $tmp -Value $importPy -NoNewline
docker cp $tmp "${containerName}:/tmp/ap_import.py" 2>$null
$importResult = docker exec $containerName python /tmp/ap_import.py 2>&1
Remove-Item $tmp -ErrorAction SilentlyContinue
Remove-Item "linkedin_cookies.json" -ErrorAction SilentlyContinue

Write-Host ""

if ($importResult -match "SESSION_VALID") {
    Write-Host "  =====================================" -ForegroundColor Green
    Write-Host "  COOKIES IMPORTED - SESSION VALID" -ForegroundColor Green
    Write-Host "  Agent ready at http://pilot.local" -ForegroundColor Cyan
    Write-Host "  =====================================" -ForegroundColor Green
} else {
    Write-Host "  Cookie import didn't establish session." -ForegroundColor Red
    Write-Host "  LinkedIn may have invalidated cookies." -ForegroundColor Yellow
    Write-Host "  Output: $importResult" -ForegroundColor Gray
}

Write-Host ""

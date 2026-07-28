#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════
# ApplyPilot — Complete Setup (Fresh to Working)
# ═══════════════════════════════════════════════════════════
# One script does everything:
#   1. Install/update Python dependencies
#   2. Match Playwright version with Docker
#   3. Install Chromium
#   4. Setup hosts file (pilot.local)
#   5. Start Docker container
#   6. Login to LinkedIn (creates session locally)
#   7. Copy session to Docker
#   8. Verify session works inside Docker
#   9. Ready to scan
# ═══════════════════════════════════════════════════════════

Write-Host ""
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host "    ApplyPilot - Complete Setup" -ForegroundColor Cyan
Write-Host "    Powered by Rahul" -ForegroundColor DarkGray
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Continue"

# ─── Step 1: Python deps ───────────────────────────────────

Write-Host "  [1/9] Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "        pip install failed. Is Python installed?" -ForegroundColor Red
    exit 1
}
Write-Host "        Done." -ForegroundColor Green

# ─── Step 2: Match Playwright version ─────────────────────

Write-Host "  [2/9] Installing Playwright 1.61.0 (matches Docker)..." -ForegroundColor Yellow
pip install playwright==1.61.0 --quiet 2>$null
Write-Host "        Done." -ForegroundColor Green

# ─── Step 3: Install Chromium ─────────────────────────────

Write-Host "  [3/9] Installing Chromium browser..." -ForegroundColor Yellow
playwright install chromium 2>$null
Write-Host "        Done." -ForegroundColor Green

# ─── Step 4: Hosts file ───────────────────────────────────

Write-Host "  [4/9] Checking pilot.local domain..." -ForegroundColor Yellow
$hostsFile = "C:\Windows\System32\drivers\etc\hosts"
$hasHost = Get-Content $hostsFile -ErrorAction SilentlyContinue | Select-String "pilot.local"
if ($hasHost) {
    Write-Host "        Already configured." -ForegroundColor Green
} else {
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if ($isAdmin) {
        Add-Content -Path $hostsFile -Value "`n127.0.0.1  pilot.local"
        Write-Host "        Added pilot.local to hosts file." -ForegroundColor Green
    } else {
        Write-Host "        Skipped (need Administrator). Run once as admin or add manually:" -ForegroundColor Yellow
        Write-Host "        127.0.0.1  pilot.local  -->  $hostsFile" -ForegroundColor Gray
    }
}

# ─── Step 5: Start Docker ─────────────────────────────────

Write-Host "  [5/9] Starting Docker container..." -ForegroundColor Yellow
docker-compose down 2>$null
docker-compose up -d --build 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "        Docker failed. Is Docker Desktop running?" -ForegroundColor Red
    exit 1
}
Start-Sleep -Seconds 5
Write-Host "        Container running." -ForegroundColor Green
$containerName = (docker ps --format "{{.Names}}" 2>$null | Select-String "applypilot").Matches.Value

# ─── Step 6: LinkedIn Login (local) ──────────────────────

Write-Host "  [6/9] LinkedIn login..." -ForegroundColor Yellow

# Check if session already exists
$sessionPaths = @(
    "$env:LOCALAPPDATA\linkedin_agent\linkedin_agent\browser_data\Default",
    "$env:LOCALAPPDATA\linkedin_agent\browser_data\Default"
)
$sessionExists = $false
$sessionDir = $null
foreach ($p in $sessionPaths) {
    if (Test-Path $p) { $sessionExists = $true; $sessionDir = (Split-Path $p); break }
}

if ($sessionExists) {
    # Quick test if existing session is valid
    $testPy = 'import asyncio' + "`n"
    $testPy += 'from linkedin_agent.browser import LinkedInBrowser' + "`n"
    $testPy += 'async def t():' + "`n"
    $testPy += '    b = LinkedInBrowser()' + "`n"
    $testPy += '    await b.launch(headless=True)' + "`n"
    $testPy += '    await b.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")' + "`n"
    $testPy += '    await asyncio.sleep(4)' + "`n"
    $testPy += '    print("VALID" if "/feed" in b.page.url and "/login" not in b.page.url else "EXPIRED")' + "`n"
    $testPy += '    await b.close()' + "`n"
    $testPy += 'asyncio.run(t())' + "`n"

    $tmp = Join-Path $env:TEMP "ap_check.py"
    Set-Content -Path $tmp -Value $testPy -NoNewline
    $check = python $tmp 2>$null
    Remove-Item $tmp -ErrorAction SilentlyContinue

    if ($check -match "VALID") {
        Write-Host "        Existing session is valid." -ForegroundColor Green
    } else {
        Write-Host "        Session expired. Opening browser for login..." -ForegroundColor Yellow
        Write-Host "        Log in to LinkedIn in the browser window." -ForegroundColor White
        Write-Host ""
        python tests/test_browser_dry_run.py --limit 1
        $sessionDir = $sessionPaths | ForEach-Object { Split-Path $_ } | Where-Object { Test-Path "$_\Default" } | Select-Object -First 1
    }
} else {
    Write-Host "        No session. Opening browser for first login..." -ForegroundColor Yellow
    Write-Host "        Log in to LinkedIn in the browser window." -ForegroundColor White
    Write-Host ""
    python tests/test_browser_dry_run.py --limit 1
    $sessionDir = $sessionPaths | ForEach-Object { Split-Path $_ } | Where-Object { Test-Path "$_\Default" } | Select-Object -First 1
}

if (-not $sessionDir) {
    Write-Host "        Could not find session after login." -ForegroundColor Red
    exit 1
}

# ─── Step 7: Transfer cookies to Docker ──────────────────

Write-Host "  [7/9] Transferring session cookies to Docker..." -ForegroundColor Yellow

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
$exportPy += '    print(f"EXPORTED {len(linkedin_cookies)}")' + "`n"
$exportPy += '    await ctx.close()' + "`n"
$exportPy += '    await pw.stop()' + "`n"
$exportPy += 'asyncio.run(export())' + "`n"

$tmp = Join-Path $env:TEMP "ap_export.py"
Set-Content -Path $tmp -Value $exportPy -NoNewline
$exportResult = python $tmp 2>$null
Remove-Item $tmp -ErrorAction SilentlyContinue

if ($exportResult -match "EXPORTED (\d+)") {
    Write-Host "        Exported $($Matches[1]) cookies." -ForegroundColor Green
} else {
    Write-Host "        Cookie export failed. Session may be invalid." -ForegroundColor Red
    Write-Host "        Run setup again after logging in." -ForegroundColor Yellow
    exit 1
}

# Copy to Docker and import
docker cp "linkedin_cookies.json" "${containerName}:/tmp/linkedin_cookies.json" 2>$null

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
$importPy += '        await page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")' + "`n"
$importPy += '        await asyncio.sleep(2)' + "`n"
$importPy += '        print("VALID")' + "`n"
$importPy += '    else:' + "`n"
$importPy += '        print("INVALID")' + "`n"
$importPy += '    await b.close()' + "`n"
$importPy += 'asyncio.run(imp())' + "`n"

$tmp = Join-Path $env:TEMP "ap_import.py"
Set-Content -Path $tmp -Value $importPy -NoNewline
docker cp $tmp "${containerName}:/tmp/ap_import.py" 2>$null
$importResult = docker exec $containerName python /tmp/ap_import.py 2>&1
Remove-Item $tmp -ErrorAction SilentlyContinue
Remove-Item "linkedin_cookies.json" -ErrorAction SilentlyContinue

# ─── Step 8: Verify inside Docker ────────────────────────

Write-Host "  [8/9] Verifying session inside Docker..." -ForegroundColor Yellow

if ($importResult -match "VALID") {
    Write-Host "        Session works inside Docker!" -ForegroundColor Green
} else {
    Write-Host "        Cookie transfer failed." -ForegroundColor Red
    Write-Host "        The agent will run natively instead." -ForegroundColor Yellow
    Write-Host "        Use: python -m linkedin_agent run --dry-run --limit 10" -ForegroundColor Gray
}

# ─── Step 9: Done ────────────────────────────────────────

Write-Host ""
Write-Host "  [9/9] Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host "  READY TO USE" -ForegroundColor Green
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Tracker:  http://pilot.local" -ForegroundColor White
Write-Host ""
Write-Host "  Run agent:" -ForegroundColor White
Write-Host "    python -m linkedin_agent run --dry-run --limit 10" -ForegroundColor Gray
Write-Host ""
Write-Host "  Scheduled:" -ForegroundColor White
Write-Host "    python -m linkedin_agent daemon --dry-run" -ForegroundColor Gray
Write-Host ""
Write-Host "  Telegram bot:" -ForegroundColor White
Write-Host "    python -m linkedin_agent.bot" -ForegroundColor Gray
Write-Host ""

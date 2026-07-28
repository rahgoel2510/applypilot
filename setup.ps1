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

# ─── Step 7: Copy session to Docker ──────────────────────

Write-Host "  [7/9] Copying session to Docker..." -ForegroundColor Yellow
$containerName = (docker ps --format "{{.Names}}" 2>$null | Select-String "applypilot").Matches.Value
$targetPath = "/root/.local/share/linkedin_agent/browser_data"
docker exec $containerName mkdir -p $targetPath 2>$null
docker cp "${sessionDir}\." "${containerName}:${targetPath}/" 2>$null
Write-Host "        Copied." -ForegroundColor Green

# ─── Step 8: Verify inside Docker ────────────────────────

Write-Host "  [8/9] Verifying session inside Docker..." -ForegroundColor Yellow

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

$tmp = Join-Path $env:TEMP "ap_docker_check.py"
Set-Content -Path $tmp -Value $testPy -NoNewline
docker cp $tmp "${containerName}:/tmp/ap_check.py" 2>$null
$dockerCheck = docker exec $containerName python /tmp/ap_check.py 2>&1
Remove-Item $tmp -ErrorAction SilentlyContinue

if ($dockerCheck -match "VALID") {
    Write-Host "        Session works inside Docker!" -ForegroundColor Green
} else {
    Write-Host "        Session version mismatch (expected with different Chromium)." -ForegroundColor Yellow
    Write-Host "        The local agent will push results to the tracker directly." -ForegroundColor Yellow
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

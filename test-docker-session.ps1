#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════
# ApplyPilot — Test LinkedIn Session INSIDE Docker
# ═══════════════════════════════════════════════════════════

Write-Host ""
Write-Host "  ApplyPilot - Docker Session Test" -ForegroundColor Cyan
Write-Host "  ==================================" -ForegroundColor Cyan
Write-Host ""

$container = "applypilot"

# Check container running
$running = docker ps --format "{{.Names}}" | Select-String -Pattern "^$container$"
if (-not $running) {
    Write-Host "  [!] Container '$container' not running." -ForegroundColor Red
    Write-Host "      Run: docker-compose up -d" -ForegroundColor Yellow
    exit 1
}
Write-Host "  [1] Container running ✓" -ForegroundColor Green

# Write test script to temp file
$testScript = @'
import asyncio, time
from linkedin_agent.browser import LinkedInBrowser

async def test():
    b = LinkedInBrowser()
    await b.launch(headless=True)
    t0 = time.time()
    page = b.page
    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    await asyncio.sleep(4)
    url = page.url
    elapsed = time.time() - t0
    if "/feed" in url and "/login" not in url:
        print(f"VALID {elapsed:.1f}s")
    else:
        print(f"EXPIRED {elapsed:.1f}s {url[:60]}")
    await b.close()

asyncio.run(test())
'@

$tempFile = [System.IO.Path]::GetTempFileName()
Set-Content -Path $tempFile -Value $testScript

# Copy and run inside container
Write-Host "  [2] Testing session inside Docker..." -ForegroundColor Yellow
docker cp $tempFile "${container}:/tmp/test_session.py" 2>$null
$result = docker exec $container python /tmp/test_session.py 2>&1
Remove-Item $tempFile -ErrorAction SilentlyContinue

Write-Host ""

if ($result -match "^VALID") {
    $time = ($result -split " ")[1]
    Write-Host "  =====================================" -ForegroundColor Green
    Write-Host "  ✅ DOCKER SESSION IS VALID!" -ForegroundColor Green
    Write-Host "     LinkedIn responded in $time" -ForegroundColor Gray
    Write-Host "  =====================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Agent is ready to scan from the UI." -ForegroundColor Cyan
    Write-Host "  Open: http://pilot.local → Agent → Start Scan" -ForegroundColor Cyan
}
elseif ($result -match "^EXPIRED") {
    $parts = $result -split " "
    Write-Host "  =====================================" -ForegroundColor Red
    Write-Host "  ❌ DOCKER SESSION EXPIRED" -ForegroundColor Red
    Write-Host "     Redirected to: $($parts[2])" -ForegroundColor Gray
    Write-Host "  =====================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Fix: Copy your local session into Docker:" -ForegroundColor Yellow
    Write-Host "    .\copy-session.ps1" -ForegroundColor White
}
else {
    Write-Host "  ⚠️  Unexpected result:" -ForegroundColor Yellow
    Write-Host "  $result" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Possible issues:" -ForegroundColor Yellow
    Write-Host "    - Chromium not installed (rebuild: docker-compose up --build)" -ForegroundColor Gray
    Write-Host "    - No session files (run: .\copy-session.ps1)" -ForegroundColor Gray
}

Write-Host ""

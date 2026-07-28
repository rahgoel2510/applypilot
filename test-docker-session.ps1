#!/usr/bin/env pwsh
# ApplyPilot - Test LinkedIn Session INSIDE Docker

Write-Host ""
Write-Host "  ApplyPilot - Docker Session Test" -ForegroundColor Cyan
Write-Host "  ==================================" -ForegroundColor Cyan
Write-Host ""

$container = "applypilot"

# Check container running
$running = docker ps --format "{{.Names}}" 2>$null | Select-String -Pattern "^applypilot$"
if (-not $running) {
    Write-Host "  Container not running. Run: docker-compose up -d" -ForegroundColor Red
    exit 1
}
Write-Host "  [1] Container running" -ForegroundColor Green

# Create test script
$pyCode = 'import asyncio, time' + "`n"
$pyCode += 'from linkedin_agent.browser import LinkedInBrowser' + "`n"
$pyCode += 'async def test():' + "`n"
$pyCode += '    b = LinkedInBrowser()' + "`n"
$pyCode += '    await b.launch(headless=True)' + "`n"
$pyCode += '    t0 = time.time()' + "`n"
$pyCode += '    page = b.page' + "`n"
$pyCode += '    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")' + "`n"
$pyCode += '    await asyncio.sleep(4)' + "`n"
$pyCode += '    url = page.url' + "`n"
$pyCode += '    elapsed = time.time() - t0' + "`n"
$pyCode += '    if "/feed" in url and "/login" not in url:' + "`n"
$pyCode += '        print(f"VALID {elapsed:.1f}s")' + "`n"
$pyCode += '    else:' + "`n"
$pyCode += '        print(f"EXPIRED {elapsed:.1f}s {url[:60]}")' + "`n"
$pyCode += '    await b.close()' + "`n"
$pyCode += 'asyncio.run(test())' + "`n"

$tempFile = Join-Path $env:TEMP "test_docker_session.py"
Set-Content -Path $tempFile -Value $pyCode -NoNewline

# Copy and run
Write-Host "  [2] Testing session inside Docker..." -ForegroundColor Yellow
docker cp $tempFile "${container}:/tmp/test_session.py" 2>$null
$result = docker exec $container python /tmp/test_session.py 2>&1
Remove-Item $tempFile -ErrorAction SilentlyContinue

Write-Host ""

if ($result -match "^VALID") {
    Write-Host "  =====================================" -ForegroundColor Green
    Write-Host "  SESSION IS VALID" -ForegroundColor Green
    Write-Host "  Agent is ready. Open http://pilot.local" -ForegroundColor Green
    Write-Host "  =====================================" -ForegroundColor Green
}
elseif ($result -match "^EXPIRED") {
    Write-Host "  =====================================" -ForegroundColor Red
    Write-Host "  SESSION EXPIRED" -ForegroundColor Red
    Write-Host "  Run: copy-session.ps1" -ForegroundColor Yellow
    Write-Host "  =====================================" -ForegroundColor Red
}
else {
    Write-Host "  Unexpected:" -ForegroundColor Yellow
    Write-Host "  $result" -ForegroundColor Gray
    Write-Host "  Try: docker-compose up --build" -ForegroundColor Yellow
}

Write-Host ""

#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════
# ApplyPilot — Login to LinkedIn INSIDE Docker
# ═══════════════════════════════════════════════════════════
# Opens a browser inside the Docker container so you can
# log in to LinkedIn. The session is saved inside Docker
# permanently (survives restarts via volume).
#
# Uses Playwright's headed mode with Xvfb (virtual display).
# ═══════════════════════════════════════════════════════════

$container = "applypilot"

Write-Host ""
Write-Host "  ApplyPilot - Docker LinkedIn Login" -ForegroundColor Cyan
Write-Host "  ====================================" -ForegroundColor Cyan
Write-Host ""

# Check container
$running = docker ps --format "{{.Names}}" 2>$null | Select-String -Pattern "^applypilot$"
if (-not $running) {
    Write-Host "  Container not running. Run: docker-compose up -d --build" -ForegroundColor Red
    exit 1
}

Write-Host "  This will open LinkedIn login inside Docker." -ForegroundColor Yellow
Write-Host "  The browser runs headless - it will auto-navigate" -ForegroundColor Yellow
Write-Host "  to LinkedIn and attempt login with your credentials." -ForegroundColor Yellow
Write-Host ""
Write-Host "  If LinkedIn requires a verification code," -ForegroundColor Yellow
Write-Host "  check your email/phone and enter it when prompted." -ForegroundColor Yellow
Write-Host ""

# Build login script
$pyCode = 'import asyncio, time, os' + "`n"
$pyCode += 'from linkedin_agent.browser import LinkedInBrowser' + "`n"
$pyCode += '' + "`n"
$pyCode += 'async def login():' + "`n"
$pyCode += '    b = LinkedInBrowser()' + "`n"
$pyCode += '    await b.launch(headless=True)' + "`n"
$pyCode += '    page = b.page' + "`n"
$pyCode += '    print("Navigating to LinkedIn feed...")' + "`n"
$pyCode += '    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")' + "`n"
$pyCode += '    await asyncio.sleep(5)' + "`n"
$pyCode += '    if "/feed" in page.url and "/login" not in page.url:' + "`n"
$pyCode += '        print("ALREADY_LOGGED_IN")' + "`n"
$pyCode += '        await b.close()' + "`n"
$pyCode += '        return' + "`n"
$pyCode += '    print("Not logged in. Attempting login...")' + "`n"
$pyCode += '    email = os.environ.get("LINKEDIN_EMAIL", "")' + "`n"
$pyCode += '    password = os.environ.get("LINKEDIN_PASSWORD", "")' + "`n"
$pyCode += '    if not email or not password:' + "`n"
$pyCode += '        print("NO_CREDENTIALS")' + "`n"
$pyCode += '        await b.close()' + "`n"
$pyCode += '        return' + "`n"
$pyCode += '    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")' + "`n"
$pyCode += '    await asyncio.sleep(3)' + "`n"
$pyCode += '    try:' + "`n"
$pyCode += '        el = page.locator("input[autocomplete=\"username\"]").first' + "`n"
$pyCode += '        await el.fill(email)' + "`n"
$pyCode += '        await asyncio.sleep(1)' + "`n"
$pyCode += '        pw = page.locator("input[type=\"password\"]").first' + "`n"
$pyCode += '        await pw.fill(password)' + "`n"
$pyCode += '        await asyncio.sleep(1)' + "`n"
$pyCode += '        await page.click("button[type=\"submit\"]")' + "`n"
$pyCode += '        print("Submitted login. Waiting for redirect...")' + "`n"
$pyCode += '        await asyncio.sleep(10)' + "`n"
$pyCode += '        url = page.url' + "`n"
$pyCode += '        if "/feed" in url:' + "`n"
$pyCode += '            print("LOGIN_SUCCESS")' + "`n"
$pyCode += '        elif "checkpoint" in url or "challenge" in url:' + "`n"
$pyCode += '            print("VERIFICATION_NEEDED")' + "`n"
$pyCode += '            print("LinkedIn needs verification. Check your email/phone.")' + "`n"
$pyCode += '            print("Waiting 60s for you to verify...")' + "`n"
$pyCode += '            await asyncio.sleep(60)' + "`n"
$pyCode += '            if "/feed" in page.url:' + "`n"
$pyCode += '                print("LOGIN_SUCCESS_AFTER_VERIFY")' + "`n"
$pyCode += '            else:' + "`n"
$pyCode += '                print("VERIFY_TIMEOUT")' + "`n"
$pyCode += '        else:' + "`n"
$pyCode += '            print(f"LOGIN_UNKNOWN url={url[:60]}")' + "`n"
$pyCode += '    except Exception as e:' + "`n"
$pyCode += '        print(f"LOGIN_ERROR {e}")' + "`n"
$pyCode += '    await b.close()' + "`n"
$pyCode += '' + "`n"
$pyCode += 'asyncio.run(login())' + "`n"

$tempFile = Join-Path $env:TEMP "docker_login.py"
Set-Content -Path $tempFile -Value $pyCode -NoNewline

# Copy and run
docker cp $tempFile "${container}:/tmp/docker_login.py" 2>$null
Remove-Item $tempFile -ErrorAction SilentlyContinue

Write-Host "  Running login inside Docker..." -ForegroundColor Yellow
Write-Host ""

$result = docker exec $container python /tmp/docker_login.py 2>&1
$lines = $result -split "`n"

foreach ($line in $lines) {
    Write-Host "  $line" -ForegroundColor Gray
}

Write-Host ""

if ($result -match "ALREADY_LOGGED_IN") {
    Write-Host "  ✅ Already logged in! Session is valid." -ForegroundColor Green
    Write-Host "     Open http://pilot.local - Agent - Start Scan" -ForegroundColor Cyan
}
elseif ($result -match "LOGIN_SUCCESS") {
    Write-Host "  ✅ Login successful! Session saved in Docker." -ForegroundColor Green
    Write-Host "     Open http://pilot.local - Agent - Start Scan" -ForegroundColor Cyan
}
elseif ($result -match "VERIFICATION_NEEDED") {
    Write-Host "  ⚠️  LinkedIn needs verification." -ForegroundColor Yellow
    Write-Host "     Check your email/phone for a code." -ForegroundColor Yellow
    Write-Host "     Run this script again after verifying." -ForegroundColor Yellow
}
elseif ($result -match "NO_CREDENTIALS") {
    Write-Host "  ❌ No LinkedIn credentials in Docker." -ForegroundColor Red
    Write-Host "     Set them in Settings: http://pilot.local/#settings" -ForegroundColor Yellow
}
else {
    Write-Host "  ⚠️  Login result unclear. Check output above." -ForegroundColor Yellow
}

Write-Host ""

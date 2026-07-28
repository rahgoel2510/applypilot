#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════
# ApplyPilot — Setup LinkedIn Session in Container
# ═══════════════════════════════════════════════════════════
# Copies your local session into the container, tests it,
# and falls back to JS-based login if copy doesn't work.
# ═══════════════════════════════════════════════════════════

$containerName = (docker ps --format "{{.Names}}" 2>$null | Select-String -Pattern "applypilot").Matches.Value

Write-Host ""
Write-Host "  ApplyPilot - LinkedIn Session Setup" -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host ""

if (-not $containerName) {
    Write-Host "  Container not running. Start with: docker-compose up -d" -ForegroundColor Red
    exit 1
}
Write-Host "  [1] Container: $containerName" -ForegroundColor Green

# Step 1: Find local session
$paths = @(
    "$env:LOCALAPPDATA\linkedin_agent\linkedin_agent\browser_data",
    "$env:LOCALAPPDATA\linkedin_agent\browser_data"
)
$sessionPath = $null
foreach ($p in $paths) {
    if (Test-Path "$p\Default") { $sessionPath = $p; break }
}

$targetPath = "/root/.local/share/linkedin_agent/browser_data"

if ($sessionPath) {
    Write-Host "  [2] Local session found: $sessionPath" -ForegroundColor Green

    # Step 2: Copy session into container
    Write-Host "  [3] Copying session into container..." -ForegroundColor Yellow
    docker exec $containerName mkdir -p $targetPath 2>$null
    docker cp "${sessionPath}\." "${containerName}:${targetPath}/" 2>$null
    Write-Host "      Copied." -ForegroundColor Gray

    # Step 3: Test if copied session works
    Write-Host "  [4] Testing copied session..." -ForegroundColor Yellow

    $testPy = 'import asyncio, time' + "`n"
    $testPy += 'from linkedin_agent.browser import LinkedInBrowser' + "`n"
    $testPy += 'async def t():' + "`n"
    $testPy += '    b = LinkedInBrowser()' + "`n"
    $testPy += '    await b.launch(headless=True)' + "`n"
    $testPy += '    await b.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")' + "`n"
    $testPy += '    await asyncio.sleep(4)' + "`n"
    $testPy += '    url = b.page.url' + "`n"
    $testPy += '    print("VALID" if "/feed" in url and "/login" not in url else "EXPIRED")' + "`n"
    $testPy += '    await b.close()' + "`n"
    $testPy += 'asyncio.run(t())' + "`n"

    $tmp = Join-Path $env:TEMP "ap_test.py"
    Set-Content -Path $tmp -Value $testPy -NoNewline
    docker cp $tmp "${containerName}:/tmp/ap_test.py" 2>$null
    $testResult = docker exec $containerName python /tmp/ap_test.py 2>&1
    Remove-Item $tmp -ErrorAction SilentlyContinue

    if ($testResult -match "VALID") {
        Write-Host "" 
        Write-Host "  =====================================" -ForegroundColor Green
        Write-Host "  SESSION READY" -ForegroundColor Green
        Write-Host "  Copied session works inside container." -ForegroundColor Green
        Write-Host "  Open http://pilot.local - Agent - Start Scan" -ForegroundColor Cyan
        Write-Host "  =====================================" -ForegroundColor Green
        Write-Host ""
        exit 0
    }

    Write-Host "      Copied session didn't work (version mismatch)." -ForegroundColor Yellow
    Write-Host "      Falling back to login inside container..." -ForegroundColor Yellow
    Write-Host ""
}
else {
    Write-Host "  [2] No local session found." -ForegroundColor Yellow
    Write-Host "      Will login directly inside container." -ForegroundColor Yellow
    Write-Host ""
}

# Step 4: Login inside container using JS fill
Write-Host "  [5] Logging in inside container..." -ForegroundColor Yellow

$loginPy = 'import asyncio, os' + "`n"
$loginPy += 'from linkedin_agent.browser import LinkedInBrowser' + "`n"
$loginPy += 'async def login():' + "`n"
$loginPy += '    b = LinkedInBrowser()' + "`n"
$loginPy += '    await b.launch(headless=True)' + "`n"
$loginPy += '    page = b.page' + "`n"
$loginPy += '    email = os.environ.get("LINKEDIN_EMAIL", "")' + "`n"
$loginPy += '    password = os.environ.get("LINKEDIN_PASSWORD", "")' + "`n"
$loginPy += '    if not email or not password:' + "`n"
$loginPy += '        print("NO_CREDENTIALS")' + "`n"
$loginPy += '        await b.close()' + "`n"
$loginPy += '        return' + "`n"
$loginPy += '    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")' + "`n"
$loginPy += '    await asyncio.sleep(3)' + "`n"
$loginPy += '    await page.evaluate(f"""() => {{' + "`n"
$loginPy += '        const inputs = document.querySelectorAll("input[autocomplete=username], input[type=email]");' + "`n"
$loginPy += '        for (const el of inputs) {{ el.value = "{email}"; el.dispatchEvent(new Event("input", {{bubbles:true}})); }}' + "`n"
$loginPy += '        const pass_inputs = document.querySelectorAll("input[type=password]");' + "`n"
$loginPy += '        for (const el of pass_inputs) {{ el.value = "{password}"; el.dispatchEvent(new Event("input", {{bubbles:true}})); }}' + "`n"
$loginPy += '    }}""")' + "`n"
$loginPy += '    await asyncio.sleep(2)' + "`n"
$loginPy += '    btn = page.locator("button[type=\"submit\"]").first' + "`n"
$loginPy += '    if await btn.is_visible():' + "`n"
$loginPy += '        await btn.click()' + "`n"
$loginPy += '    else:' + "`n"
$loginPy += '        await page.keyboard.press("Enter")' + "`n"
$loginPy += '    print("Submitted. Waiting for redirect...")' + "`n"
$loginPy += '    await asyncio.sleep(15)' + "`n"
$loginPy += '    url = page.url' + "`n"
$loginPy += '    if "/feed" in url:' + "`n"
$loginPy += '        print("LOGIN_SUCCESS")' + "`n"
$loginPy += '    elif "checkpoint" in url or "challenge" in url:' + "`n"
$loginPy += '        print("VERIFICATION_NEEDED")' + "`n"
$loginPy += '        print("Check email/phone. Waiting 90s...")' + "`n"
$loginPy += '        await asyncio.sleep(90)' + "`n"
$loginPy += '        if "/feed" in page.url:' + "`n"
$loginPy += '            print("LOGIN_SUCCESS")' + "`n"
$loginPy += '        else:' + "`n"
$loginPy += '            print("VERIFY_TIMEOUT")' + "`n"
$loginPy += '    else:' + "`n"
$loginPy += '        print(f"LOGIN_UNKNOWN {url[:60]}")' + "`n"
$loginPy += '    await b.close()' + "`n"
$loginPy += 'asyncio.run(login())' + "`n"

$tmp = Join-Path $env:TEMP "ap_login.py"
Set-Content -Path $tmp -Value $loginPy -NoNewline
docker cp $tmp "${containerName}:/tmp/ap_login.py" 2>$null
$loginResult = docker exec $containerName python /tmp/ap_login.py 2>&1
Remove-Item $tmp -ErrorAction SilentlyContinue

foreach ($line in ($loginResult -split "`n")) {
    Write-Host "      $line" -ForegroundColor Gray
}

Write-Host ""

if ($loginResult -match "LOGIN_SUCCESS") {
    Write-Host "  =====================================" -ForegroundColor Green
    Write-Host "  LOGIN SUCCESSFUL" -ForegroundColor Green
    Write-Host "  Session saved in container." -ForegroundColor Green
    Write-Host "  Open http://pilot.local - Agent - Start Scan" -ForegroundColor Cyan
    Write-Host "  =====================================" -ForegroundColor Green
}
elseif ($loginResult -match "VERIFICATION_NEEDED") {
    Write-Host "  LinkedIn needs verification." -ForegroundColor Yellow
    Write-Host "  Check email/phone, approve it, then run this again." -ForegroundColor Yellow
}
elseif ($loginResult -match "NO_CREDENTIALS") {
    Write-Host "  No credentials found in container." -ForegroundColor Red
    Write-Host "  Set them at: http://pilot.local/#settings" -ForegroundColor Yellow
}
else {
    Write-Host "  Login unclear. See output above." -ForegroundColor Yellow
}

Write-Host ""

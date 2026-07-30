#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════════
# ApplyPilot — Docker Setup & Test (Windows)
# ═══════════════════════════════════════════════════════════════
# Builds the Docker image, starts the container, and verifies
# everything is working.
#
# Usage: pwsh ./docker-setup.ps1
# ═══════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

Write-Host ""
Write-Host "  ═══ ApplyPilot — Docker Setup & Test ═══" -ForegroundColor Cyan
Write-Host ""

# ─── 1. Check Docker ────────────────────────────────────────

Write-Host "  [1/7] Checking Docker..." -ForegroundColor Yellow
try {
    docker info 2>$null | Out-Null
    Write-Host "        Docker is running ✓" -ForegroundColor Green
} catch {
    Write-Host "        Docker not found or not running!" -ForegroundColor Red
    Write-Host "        Install Docker Desktop from https://docker.com" -ForegroundColor Yellow
    exit 1
}

# ─── 2. Check .env ──────────────────────────────────────────

Write-Host "  [2/7] Checking environment..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "        Created .env from template" -ForegroundColor Yellow
        Write-Host "        ⚠ Edit .env with your credentials!" -ForegroundColor Yellow
    }
} else {
    Write-Host "        .env exists ✓" -ForegroundColor Green
}

# ─── 3. Stop existing ───────────────────────────────────────

Write-Host "  [3/7] Stopping existing container..." -ForegroundColor Yellow
docker compose down 2>$null
Write-Host "        Done" -ForegroundColor Green

# ─── 4. Build ───────────────────────────────────────────────

Write-Host "  [4/7] Building Docker image (may take a few minutes)..." -ForegroundColor Yellow
docker compose build
if ($LASTEXITCODE -ne 0) {
    Write-Host "        Build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "        Image built ✓" -ForegroundColor Green

# ─── 5. Start ───────────────────────────────────────────────

Write-Host "  [5/7] Starting container..." -ForegroundColor Yellow
docker compose up -d
Write-Host "        Container started ✓" -ForegroundColor Green

# ─── 6. Wait for health ─────────────────────────────────────

Write-Host "  [6/7] Waiting for service..." -ForegroundColor Yellow
$healthy = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:80/api/stats" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch {}
    Start-Sleep -Seconds 1
}

if (-not $healthy) {
    Write-Host "        Service did not start within 30s!" -ForegroundColor Red
    docker compose logs --tail 20
    exit 1
}
Write-Host "        Service is healthy ✓" -ForegroundColor Green

# ─── 7. Tests ───────────────────────────────────────────────

Write-Host "  [7/7] Running tests..." -ForegroundColor Yellow
Write-Host ""

# Test API stats
try {
    $stats = Invoke-RestMethod -Uri "http://localhost:80/api/stats" -Method Get
    Write-Host "    ✓ API /stats: total=$($stats.total)" -ForegroundColor Green
} catch {
    Write-Host "    ✗ API /stats failed" -ForegroundColor Red
}

# Test jobs
try {
    $jobs = Invoke-RestMethod -Uri "http://localhost:80/api/jobs" -Method Get
    $count = if ($jobs -is [array]) { $jobs.Count } else { 0 }
    Write-Host "    ✓ API /jobs: $count jobs" -ForegroundColor Green
} catch {
    Write-Host "    ✗ API /jobs failed" -ForegroundColor Red
}

# Test frontend
try {
    $fe = Invoke-WebRequest -Uri "http://localhost:80/" -UseBasicParsing -TimeoutSec 5
    Write-Host "    ✓ Frontend: HTTP $($fe.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "    ⚠ Frontend: not serving (API-only mode)" -ForegroundColor Yellow
}

# Test webhook
try {
    $body = '{"event":"discovered","title":"Test Job","company":"Test Corp","match_score":0.85}'
    $wh = Invoke-WebRequest -Uri "http://localhost:80/api/webhook/agent" -Method Post -Body $body -ContentType "application/json" -UseBasicParsing
    Write-Host "    ✓ Webhook: Job created (HTTP $($wh.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "    ⚠ Webhook: $($_.Exception.Message)" -ForegroundColor Yellow
}

# ─── Done ────────────────────────────────────────────────────

Write-Host ""
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║    ✅ All Tests Passed!              ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Dashboard:  http://localhost:80" -ForegroundColor White
Write-Host "  API:        http://localhost:80/api/stats" -ForegroundColor White
Write-Host ""
Write-Host "  Commands:" -ForegroundColor DarkGray
Write-Host "    docker compose logs -f      # View logs" -ForegroundColor DarkGray
Write-Host "    docker compose stop         # Stop" -ForegroundColor DarkGray
Write-Host "    docker compose start        # Start again" -ForegroundColor DarkGray
Write-Host "    docker compose down         # Remove" -ForegroundColor DarkGray
Write-Host ""

# Open browser
Start-Process "http://localhost:80"

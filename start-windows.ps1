#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════
# ApplyPilot — Start (Windows PowerShell)
# ═══════════════════════════════════════════════════════════

Write-Host ""
Write-Host "  ╔═══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║   ApplyPilot — Powered by Rahul      ║" -ForegroundColor Cyan
Write-Host "  ╚═══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Start tracker in Docker
Write-Host "[1/3] Starting tracker (Docker)..." -ForegroundColor Yellow
docker-compose up -d --build 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker failed. Is Docker Desktop running?" -ForegroundColor Red
    exit 1
}
Write-Host "      Tracker: http://localhost:8000" -ForegroundColor Green
Write-Host ""

# Check LinkedIn session
Write-Host "[2/3] Checking LinkedIn session..." -ForegroundColor Yellow
$sessionPath = "$env:LOCALAPPDATA\linkedin_agent\linkedin_agent\browser_data\Default"
if (Test-Path $sessionPath) {
    Write-Host "      Session found ✓" -ForegroundColor Green
} else {
    Write-Host "      No session! Running browser for first-time login..." -ForegroundColor Red
    python tests/test_browser_dry_run.py --limit 1
    Write-Host "      Session created. Continuing..." -ForegroundColor Green
}
Write-Host ""

# Run agent
Write-Host "[3/3] Starting agent scan..." -ForegroundColor Yellow
Write-Host "      Keywords: Engineering Manager, TPM, Sr Eng Manager, Director of Eng" -ForegroundColor Gray
Write-Host "      Mode: dry-run | Limit: 10 | Threshold: 80%" -ForegroundColor Gray
Write-Host "      Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

python -m linkedin_agent run --dry-run --limit 10

Write-Host ""
Write-Host "Done! Check http://localhost:8000 for results." -ForegroundColor Green

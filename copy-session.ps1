#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════
# ApplyPilot — Copy LinkedIn Session into Docker
# ═══════════════════════════════════════════════════════════
# Run this after docker-compose up to copy your local
# LinkedIn browser session into the container.
# ═══════════════════════════════════════════════════════════

$container = "applypilot"
$targetPath = "/root/.local/share/linkedin_agent/browser_data"

Write-Host ""
Write-Host "  ApplyPilot - Copy Session to Docker" -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host ""

# Find local session
$paths = @(
    "$env:LOCALAPPDATA\linkedin_agent\linkedin_agent\browser_data",
    "$env:LOCALAPPDATA\linkedin_agent\browser_data"
)

$sessionPath = $null
foreach ($p in $paths) {
    if (Test-Path "$p\Default") {
        $sessionPath = $p
        break
    }
}

if (-not $sessionPath) {
    Write-Host "  [!] No local session found." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Run this first to log in:" -ForegroundColor Yellow
    Write-Host "    python tests/test_browser_dry_run.py --limit 1" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

Write-Host "  [1] Session found: $sessionPath" -ForegroundColor Green

# Check if container is running
$running = docker ps --format "{{.Names}}" | Select-String -Pattern "^$container$"
if (-not $running) {
    Write-Host "  [!] Container '$container' is not running." -ForegroundColor Red
    Write-Host "      Start it: docker-compose up -d" -ForegroundColor Yellow
    exit 1
}

Write-Host "  [2] Container '$container' is running" -ForegroundColor Green

# Copy session
Write-Host "  [3] Copying session..." -ForegroundColor Yellow
docker exec $container mkdir -p $targetPath 2>$null
docker cp "${sessionPath}" "${container}:${targetPath}/../"

# Verify
$check = docker exec $container ls "$targetPath/Default" 2>$null
if ($check) {
    Write-Host "  [4] Session copied successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Restarting container..." -ForegroundColor Yellow
    docker restart $container | Out-Null
    Start-Sleep -Seconds 3
    Write-Host ""
    Write-Host "  ✅ Done! Open http://pilot.local" -ForegroundColor Green
    Write-Host "     Go to Agent tab → Start Scan" -ForegroundColor Cyan
} else {
    Write-Host "  [!] Copy may have failed. Check manually:" -ForegroundColor Red
    Write-Host "      docker exec $container ls $targetPath" -ForegroundColor Gray
}

Write-Host ""

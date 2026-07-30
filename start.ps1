#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════════
# ApplyPilot — Start All Services (Windows)
# Usage: pwsh ./start.ps1
# ═══════════════════════════════════════════════════════════════

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

Write-Host ""
Write-Host "  🚀 Starting ApplyPilot..." -ForegroundColor Cyan
Write-Host ""

# Activate venv
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
} elseif (Test-Path ".venv/bin/Activate.ps1") {
    & ./.venv/bin/Activate.ps1
}

# Load .env
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

# Kill existing processes
Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue | Stop-Process -Force 2>$null
Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*vite*" } 2>$null | Stop-Process -Force 2>$null
Start-Sleep -Seconds 1

# Start backend
Write-Host "  📡 Starting backend (port 8000)..." -ForegroundColor Yellow
$backend = Start-Process -FilePath "uvicorn" -ArgumentList "main:app --reload --port 8000" -WorkingDirectory "$ProjectDir\tracker\backend" -PassThru -WindowStyle Hidden -RedirectStandardOutput "$env:TEMP\applypilot-backend.log" -RedirectStandardError "$env:TEMP\applypilot-backend-err.log"
Write-Host "     PID: $($backend.Id)" -ForegroundColor DarkGray

# Start frontend
Write-Host "  🎨 Starting frontend (port 5173)..." -ForegroundColor Yellow
$frontend = Start-Process -FilePath "npx" -ArgumentList "vite --port 5173" -WorkingDirectory "$ProjectDir\tracker\frontend" -PassThru -WindowStyle Hidden -RedirectStandardOutput "$env:TEMP\applypilot-frontend.log" -RedirectStandardError "$env:TEMP\applypilot-frontend-err.log"
Write-Host "     PID: $($frontend.Id)" -ForegroundColor DarkGray

Start-Sleep -Seconds 4

Write-Host ""
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║    ✅ ApplyPilot is running!         ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Dashboard:  http://localhost:5173" -ForegroundColor White
Write-Host "  API:        http://localhost:8000" -ForegroundColor White
Write-Host ""
Write-Host "  Backend PID:  $($backend.Id)" -ForegroundColor DarkGray
Write-Host "  Frontend PID: $($frontend.Id)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  To stop:" -ForegroundColor DarkGray
Write-Host "    Stop-Process -Id $($backend.Id); Stop-Process -Id $($frontend.Id)" -ForegroundColor DarkGray
Write-Host ""

# Open browser
Start-Process "http://localhost:5173"

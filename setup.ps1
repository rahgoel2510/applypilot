#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════════
# ApplyPilot — Local Setup (Windows/macOS PowerShell)
# ═══════════════════════════════════════════════════════════════
# Run this on a fresh machine to set up everything locally.
# No Docker required.
#
# Usage: pwsh ./setup.ps1
# ═══════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║    ApplyPilot — Local Setup          ║" -ForegroundColor Cyan
Write-Host "  ║    Powered by Rahul                  ║" -ForegroundColor DarkGray
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

# ─── Step 1: Check Python ──────────────────────────────────

Write-Host "  [1/6] Checking Python..." -ForegroundColor Yellow

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "3\.(1[1-9]|[2-9]\d)") {
            $pythonCmd = $cmd
            Write-Host "        Found: $ver" -ForegroundColor Green
            break
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Host "        Python 3.11+ not found!" -ForegroundColor Red
    Write-Host "        Install from: https://python.org/downloads" -ForegroundColor Yellow
    Write-Host "        Make sure to check 'Add to PATH' during install." -ForegroundColor Yellow
    exit 1
}

# ─── Step 2: Create virtual environment ────────────────────

Write-Host "  [2/6] Setting up virtual environment..." -ForegroundColor Yellow

if (-not (Test-Path ".venv")) {
    & $pythonCmd -m venv .venv
    Write-Host "        Created .venv" -ForegroundColor Green
} else {
    Write-Host "        .venv already exists" -ForegroundColor Green
}

# Activate venv
if ($IsWindows -or $env:OS -eq "Windows_NT") {
    & .\.venv\Scripts\Activate.ps1
} else {
    & ./.venv/bin/Activate.ps1
}
Write-Host "        Virtual env activated" -ForegroundColor Green

# ─── Step 3: Install Python dependencies ──────────────────

Write-Host "  [3/6] Installing Python packages..." -ForegroundColor Yellow

pip install --upgrade pip --quiet 2>$null
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "        pip install failed!" -ForegroundColor Red
    exit 1
}

# Backend deps
if (Test-Path "tracker/backend/requirements.txt") {
    pip install -r tracker/backend/requirements.txt --quiet 2>$null
}

Write-Host "        Python packages installed" -ForegroundColor Green

# ─── Step 4: Install Playwright browser ───────────────────

Write-Host "  [4/6] Installing Playwright Chromium..." -ForegroundColor Yellow

python -m playwright install chromium 2>$null
if ($LASTEXITCODE -ne 0) {
    pip install playwright --quiet
    python -m playwright install chromium
}
Write-Host "        Chromium installed" -ForegroundColor Green

# ─── Step 5: Check Node.js & install frontend ────────────

Write-Host "  [5/6] Setting up frontend..." -ForegroundColor Yellow

try {
    $nodeVer = node --version 2>&1
    Write-Host "        Node.js $nodeVer found" -ForegroundColor Green
} catch {
    Write-Host "        Node.js not found!" -ForegroundColor Red
    Write-Host "        Install from: https://nodejs.org" -ForegroundColor Yellow
    exit 1
}

Set-Location "tracker/frontend"
npm install --silent 2>$null
Write-Host "        Frontend packages installed" -ForegroundColor Green
Set-Location $ProjectDir

# ─── Step 6: Environment file ────────────────────────────

Write-Host "  [6/6] Checking environment..." -ForegroundColor Yellow

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "        Created .env from template" -ForegroundColor Yellow
        Write-Host "        ⚠ Edit .env with your credentials!" -ForegroundColor Yellow
    }
} else {
    Write-Host "        .env exists" -ForegroundColor Green
}

# ─── Done! ───────────────────────────────────────────────

Write-Host ""
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║    ✅ Setup Complete!                ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  To start the app:" -ForegroundColor White
Write-Host ""
Write-Host "    # Terminal 1 — Backend" -ForegroundColor DarkGray
Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "    cd tracker/backend" -ForegroundColor Cyan
Write-Host "    uvicorn main:app --reload --port 8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "    # Terminal 2 — Frontend" -ForegroundColor DarkGray
Write-Host "    cd tracker/frontend" -ForegroundColor Cyan
Write-Host "    npm run dev" -ForegroundColor Cyan
Write-Host ""
Write-Host "    # Terminal 3 — Agent (optional)" -ForegroundColor DarkGray
Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "    python -m linkedin_agent serve --dry-run" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Dashboard: http://localhost:5173" -ForegroundColor White
Write-Host ""

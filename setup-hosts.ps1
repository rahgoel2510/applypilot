#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════
# ApplyPilot — Setup pilot.local domain (run as Administrator)
# ═══════════════════════════════════════════════════════════

$hostsFile = "C:\Windows\System32\drivers\etc\hosts"
$entry = "127.0.0.1  pilot.local"

# Check if already added
$content = Get-Content $hostsFile -ErrorAction SilentlyContinue
if ($content -match "pilot\.local") {
    Write-Host "✅ pilot.local is already configured." -ForegroundColor Green
    Write-Host "   Access: http://pilot.local" -ForegroundColor Cyan
    exit
}

# Need admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "❌ Run this script as Administrator!" -ForegroundColor Red
    Write-Host "   Right-click PowerShell → 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Add entry
Add-Content -Path $hostsFile -Value "`n$entry"
Write-Host "✅ Added: $entry" -ForegroundColor Green
Write-Host "   Access: http://pilot.local" -ForegroundColor Cyan

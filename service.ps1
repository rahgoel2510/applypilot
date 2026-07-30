#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════════
# ApplyPilot — Run as Background Service (Windows)
# ═══════════════════════════════════════════════════════════════
# Registers as a Windows Task Scheduler job that auto-starts on login.
#
# Usage:
#   pwsh ./service.ps1 install     # Install & start as background service
#   pwsh ./service.ps1 start       # Start the service
#   pwsh ./service.ps1 stop        # Stop the service
#   pwsh ./service.ps1 status      # Check if running
#   pwsh ./service.ps1 logs        # View logs
#   pwsh ./service.ps1 uninstall   # Remove the service
# ═══════════════════════════════════════════════════════════════

param(
    [Parameter(Position=0)]
    [ValidateSet("install", "start", "stop", "status", "logs", "uninstall")]
    [string]$Command = "status"
)

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "ApplyPilot-Tracker"
$LogDir = Join-Path $ProjectDir "logs"
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$UvicornPath = Join-Path $ProjectDir ".venv\Scripts\uvicorn.exe"
$BackendDir = Join-Path $ProjectDir "tracker\backend"
$LogFile = Join-Path $LogDir "backend.log"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Install-Service {
    Write-Host "  Installing ApplyPilot as background service..." -ForegroundColor Cyan

    # Create a wrapper script that the task will run
    $wrapperScript = Join-Path $ProjectDir "service-worker.ps1"
    @"
Set-Location "$BackendDir"
`$env:PYTHONPATH = "$ProjectDir"
`$env:PATH = "$ProjectDir\.venv\Scripts;" + `$env:PATH
& "$UvicornPath" main:app --host 0.0.0.0 --port 8000 2>&1 | Tee-Object -FilePath "$LogFile" -Append
"@ | Set-Content $wrapperScript

    # Remove existing task if any
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    # Create scheduled task that runs at logon
    $action = New-ScheduledTaskAction -Execute "pwsh.exe" -Argument "-WindowStyle Hidden -File `"$wrapperScript`""
    $trigger = New-ScheduledTaskTrigger -AtLogon
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Limited -LogonType Interactive

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null

    # Start it now
    Start-ScheduledTask -TaskName $TaskName

    Write-Host ""
    Write-Host "  ✅ Service installed!" -ForegroundColor Green
    Write-Host "     URL: http://localhost:8000" -ForegroundColor White
    Write-Host "     Auto-starts on login ✓" -ForegroundColor DarkGray
    Write-Host "     Logs: $LogFile" -ForegroundColor DarkGray
    Write-Host ""
}

function Uninstall-Service {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    $wrapper = Join-Path $ProjectDir "service-worker.ps1"
    Remove-Item $wrapper -ErrorAction SilentlyContinue
    Write-Host "  ✅ Service uninstalled" -ForegroundColor Green
}

function Start-Service-Task {
    try {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "  ✅ Service started — http://localhost:8000" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Failed to start. Run 'install' first." -ForegroundColor Red
    }
}

function Stop-Service-Task {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    # Also kill uvicorn if running
    Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "  ✅ Service stopped" -ForegroundColor Green
}

function Get-Service-Status {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task -and $task.State -eq "Running") {
        Write-Host "  ● Service is RUNNING" -ForegroundColor Green
        Write-Host "    URL: http://localhost:8000" -ForegroundColor White
        # Check if port is actually open
        $conn = Test-NetConnection -ComputerName localhost -Port 8000 -WarningAction SilentlyContinue
        if ($conn.TcpTestSucceeded) {
            Write-Host "    Health: OK ✓" -ForegroundColor Green
        } else {
            Write-Host "    Health: Port not responding (starting up?)" -ForegroundColor Yellow
        }
    } elseif ($task) {
        Write-Host "  ○ Service is STOPPED (installed)" -ForegroundColor Yellow
    } else {
        Write-Host "  ○ Service not installed" -ForegroundColor DarkGray
        Write-Host "    Run: pwsh ./service.ps1 install" -ForegroundColor DarkGray
    }
}

function Show-Logs {
    if (Test-Path $LogFile) {
        Get-Content $LogFile -Tail 50 -Wait
    } else {
        Write-Host "  No logs yet. Start the service first." -ForegroundColor DarkGray
    }
}

# ─── Dispatch ────────────────────────────────────────────────

switch ($Command) {
    "install"   { Install-Service }
    "uninstall" { Uninstall-Service }
    "start"     { Start-Service-Task }
    "stop"      { Stop-Service-Task }
    "status"    { Get-Service-Status }
    "logs"      { Show-Logs }
}

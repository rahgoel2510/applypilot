#Requires -RunAsAdministrator
<#
.SYNOPSIS
    ApplyPilot — One-Click Windows VM Deployment Script
.DESCRIPTION
    Fully automated setup for a fresh Windows 10/11 VM.
    Installs all dependencies, configures the system for always-on operation,
    and registers ApplyPilot as a background service.
.NOTES
    Safe to re-run (idempotent). Requires Administrator privileges.
    Tested on Windows 10 22H2+ and Windows 11.
#>

param(
    [switch]$SkipVSCode,
    [switch]$SkipAutoLogin,
    [switch]$SkipReboot,
    [string]$InstallPath = "C:\ApplyPilot"
)

# ─── STRICT MODE ────────────────────────────────────────────────────────────────
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "Continue"

# ─── BANNER ─────────────────────────────────────────────────────────────────────
function Show-Banner {
    $banner = @"

    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║              █████╗ ██████╗ ██████╗ ██╗  ██╗   ██╗       ║
    ║             ██╔══██╗██╔══██╗██╔══██╗██║  ╚██╗ ██╔╝       ║
    ║             ███████║██████╔╝██████╔╝██║   ╚████╔╝        ║
    ║             ██╔══██║██╔═══╝ ██╔═══╝ ██║    ╚██╔╝         ║
    ║             ██║  ██║██║     ██║     ███████╗██║           ║
    ║             ╚═╝  ╚═╝╚═╝     ╚═╝     ╚══════╝╚═╝           ║
    ║                                                           ║
    ║            ApplyPilot VM Setup — v1.0                     ║
    ║            Windows 10/11 One-Click Deployment             ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝

"@
    Write-Host $banner -ForegroundColor Cyan
}

# ─── HELPER FUNCTIONS ────────────────────────────────────────────────────────────
function Write-Step { param([string]$Message) Write-Host "`n▶ $Message" -ForegroundColor Green }
function Write-Info { param([string]$Message) Write-Host "  ℹ $Message" -ForegroundColor Gray }
function Write-Warn { param([string]$Message) Write-Host "  ⚠ $Message" -ForegroundColor Yellow }
function Write-Err  { param([string]$Message) Write-Host "  ✖ $Message" -ForegroundColor Red }
function Write-Ok   { param([string]$Message) Write-Host "  ✔ $Message" -ForegroundColor Green }

function Test-CommandExists { param([string]$Command) return [bool](Get-Command $Command -ErrorAction SilentlyContinue) }

# ─── PHASE 1: PREREQUISITES ─────────────────────────────────────────────────────
function Assert-Prerequisites {
    Write-Step "Checking prerequisites..."

    # Admin check
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Err "This script must be run as Administrator."
        Write-Info "Right-click PowerShell → 'Run as Administrator' and try again."
        exit 1
    }
    Write-Ok "Running as Administrator"

    # Windows version check
    $os = Get-CimInstance Win32_OperatingSystem
    $build = [int]$os.BuildNumber
    if ($build -lt 19041) {
        Write-Err "Windows 10 2004+ or Windows 11 required (build 19041+). Current: $build"
        exit 1
    }
    Write-Ok "Windows version: $($os.Caption) (Build $build)"

    # Internet connectivity
    try {
        $null = Invoke-WebRequest -Uri "https://github.com" -UseBasicParsing -TimeoutSec 10
        Write-Ok "Internet connectivity confirmed"
    } catch {
        Write-Err "No internet connection. Cannot proceed."
        exit 1
    }

    # Disk space (need at least 5GB free)
    $drive = Get-PSDrive C
    $freeGB = [math]::Round($drive.Free / 1GB, 1)
    if ($freeGB -lt 5) {
        Write-Err "Insufficient disk space: ${freeGB}GB free. Need at least 5GB."
        exit 1
    }
    Write-Ok "Disk space available: ${freeGB}GB"
}

# ─── PHASE 2: INSTALL CHOCOLATEY ────────────────────────────────────────────────
function Install-Chocolatey {
    Write-Step "Installing Chocolatey package manager..."

    if (Test-CommandExists "choco") {
        Write-Ok "Chocolatey already installed ($(choco --version))"
        return
    }

    try {
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        Write-Ok "Chocolatey installed successfully"
    } catch {
        Write-Err "Failed to install Chocolatey: $_"
        exit 1
    }
}

# ─── PHASE 3: INSTALL SOFTWARE ───────────────────────────────────────────────────
function Install-Software {
    Write-Step "Installing required software via Chocolatey..."

    $packages = @(
        @{ Name = "git";         Id = "git";         Check = "git" }
        @{ Name = "Python 3.11"; Id = "python311";   Check = "python" }
        @{ Name = "Node.js LTS"; Id = "nodejs-lts";  Check = "node" }
    )

    if (-not $SkipVSCode) {
        $packages += @{ Name = "VS Code"; Id = "vscode"; Check = "code" }
    }

    $total = $packages.Count
    $current = 0

    foreach ($pkg in $packages) {
        $current++
        $pct = [int](($current / $total) * 100)
        Write-Progress -Activity "Installing Software" -Status "$($pkg.Name)" -PercentComplete $pct

        if (Test-CommandExists $pkg.Check) {
            Write-Ok "$($pkg.Name) already installed"
            continue
        }

        try {
            Write-Info "Installing $($pkg.Name)..."
            choco install $pkg.Id -y --no-progress 2>&1 | Out-Null
            Write-Ok "$($pkg.Name) installed"
        } catch {
            Write-Err "Failed to install $($pkg.Name): $_"
            exit 1
        }
    }

    Write-Progress -Activity "Installing Software" -Completed

    # Refresh PATH after installations
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    Write-Ok "All software packages installed. PATH refreshed."
}

# ─── PHASE 4: CLONE OR UPDATE REPOSITORY ────────────────────────────────────────
function Install-Repository {
    Write-Step "Setting up ApplyPilot repository..."

    $repoUrl = "https://github.com/rahgoel2510/applypilot.git"

    if (Test-Path "$InstallPath\.git") {
        Write-Info "Repository exists. Pulling latest changes..."
        try {
            Push-Location $InstallPath
            git pull --ff-only 2>&1 | Out-Null
            Pop-Location
            Write-Ok "Repository updated"
        } catch {
            Pop-Location
            Write-Warn "Git pull failed. Continuing with existing code."
        }
    } else {
        if (Test-Path $InstallPath) {
            Write-Info "Directory exists but is not a git repo. Backing up..."
            Rename-Item $InstallPath "$InstallPath.bak.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        }

        try {
            Write-Info "Cloning repository to $InstallPath..."
            git clone $repoUrl $InstallPath 2>&1 | Out-Null
            Write-Ok "Repository cloned to $InstallPath"
        } catch {
            Write-Err "Failed to clone repository: $_"
            exit 1
        }
    }
}

# ─── PHASE 5: SETUP PROJECT ─────────────────────────────────────────────────────
function Install-ProjectDeps {
    Write-Step "Installing project dependencies..."

    Push-Location $InstallPath

    try {
        # Python virtual environment
        Write-Info "Creating Python virtual environment..."
        if (-not (Test-Path "venv")) {
            python -m venv venv 2>&1 | Out-Null
        }
        Write-Ok "Virtual environment ready"

        # Activate venv and install Python deps
        Write-Info "Installing Python dependencies..."
        & ".\venv\Scripts\pip.exe" install --upgrade pip --quiet 2>&1 | Out-Null
        if (Test-Path "requirements.txt") {
            & ".\venv\Scripts\pip.exe" install -r requirements.txt --quiet 2>&1 | Out-Null
        }
        Write-Ok "Python dependencies installed"

        # Install Playwright Chromium
        Write-Info "Installing Playwright Chromium (this may take a few minutes)..."
        & ".\venv\Scripts\python.exe" -m playwright install chromium 2>&1 | Out-Null
        Write-Ok "Playwright Chromium installed"

        # Node.js dependencies (for dashboard)
        if (Test-Path "frontend\package.json") {
            Write-Info "Installing Node.js dependencies for dashboard..."
            Push-Location "frontend"
            npm install --silent 2>&1 | Out-Null
            Pop-Location
            Write-Ok "Node.js dependencies installed"
        } elseif (Test-Path "package.json") {
            Write-Info "Installing Node.js dependencies..."
            npm install --silent 2>&1 | Out-Null
            Write-Ok "Node.js dependencies installed"
        }

    } catch {
        Write-Err "Dependency installation failed: $_"
        Pop-Location
        exit 1
    }

    Pop-Location
}

# ─── PHASE 6: CONFIGURE ENVIRONMENT ─────────────────────────────────────────────
function Set-Environment {
    Write-Step "Configuring environment..."

    $envFile = Join-Path $InstallPath ".env"
    $envExample = Join-Path $InstallPath ".env.example"

    if (Test-Path $envFile) {
        Write-Info ".env already exists. Skipping credential prompts."
        Write-Ok "Using existing .env configuration"
        return
    }

    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
    } else {
        New-Item -Path $envFile -ItemType File -Force | Out-Null
    }

    Write-Host "`n  ─── Credential Setup ───" -ForegroundColor Cyan
    Write-Info "Enter your credentials below (stored locally in .env only):`n"

    $linkedinEmail = Read-Host "  LinkedIn Email"
    $linkedinPass  = Read-Host "  LinkedIn Password" -AsSecureString
    $linkedinPassPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($linkedinPass))

    $telegramToken = Read-Host "  Telegram Bot Token (from @BotFather)"
    $telegramChat  = Read-Host "  Telegram Chat ID"
    $openaiKey     = Read-Host "  OpenRouter API Key (OPENAI_API_KEY)"

    # Write to .env file
    $envContent = @"
LINKEDIN_EMAIL=$linkedinEmail
LINKEDIN_PASSWORD=$linkedinPassPlain
TELEGRAM_BOT_TOKEN=$telegramToken
TELEGRAM_CHAT_ID=$telegramChat
OPENAI_API_KEY=$openaiKey
"@
    Set-Content -Path $envFile -Value $envContent -Encoding UTF8
    Write-Ok "Credentials saved to .env (never leaves this machine)"
}

# ─── PHASE 7: REGISTER WINDOWS SERVICES (TASK SCHEDULER) ────────────────────────
function Register-Services {
    Write-Step "Registering Windows scheduled tasks..."

    $taskFolder = "\ApplyPilot"

    # Ensure task folder exists (ignore if already exists)
    try {
        $null = New-Item -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\TaskCache\Tree\ApplyPilot" -Force -ErrorAction SilentlyContinue
    } catch { }

    # --- Task 1: Main Service (start on login) ---
    $taskName = "ApplyPilot-Service"
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }

    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$InstallPath\start.ps1`"" `
        -WorkingDirectory $InstallPath

    $trigger = New-ScheduledTaskTrigger -AtLogon
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1)

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -RunLevel Highest -Description "ApplyPilot main service" | Out-Null
    Write-Ok "Task registered: $taskName (starts on login)"

    # --- Task 2: Watchdog (every 5 minutes) ---
    $taskName = "ApplyPilot-Watchdog"
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }

    $watchdogScript = Join-Path $InstallPath "watchdog.ps1"
    $watchdogContent = @'
# ApplyPilot Watchdog — checks if service is alive, restarts if not
$ErrorActionPreference = "SilentlyContinue"
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/stats" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -ne 200) { throw "Unhealthy" }
} catch {
    # Service is down — restart it
    $task = Get-ScheduledTask -TaskName "ApplyPilot-Service" -ErrorAction SilentlyContinue
    if ($task) { Start-ScheduledTask -TaskName "ApplyPilot-Service" }
}
'@
    Set-Content -Path $watchdogScript -Value $watchdogContent -Encoding UTF8

    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$watchdogScript`"" `
        -WorkingDirectory $InstallPath

    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -RunLevel Highest -Description "ApplyPilot health watchdog" | Out-Null
    Write-Ok "Task registered: $taskName (every 5 minutes)"

    # --- Task 3: Weekly reboot (Sunday 3AM) ---
    $taskName = "ApplyPilot-WeeklyReboot"
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }

    $action = New-ScheduledTaskAction -Execute "shutdown.exe" -Argument "/r /t 60 /c `"ApplyPilot weekly maintenance reboot`""
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "3:00AM"
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -RunLevel Highest -Description "Weekly VM reboot for memory cleanup" | Out-Null
    Write-Ok "Task registered: $taskName (Sunday 3:00 AM)"
}

# ─── PHASE 8: CONFIGURE WINDOWS FOR ALWAYS-ON ───────────────────────────────────
function Set-AlwaysOn {
    Write-Step "Configuring Windows for always-on operation..."

    # Set High Performance power plan
    try {
        $highPerf = powercfg /list | Select-String "High performance"
        if ($highPerf -match "([a-f0-9\-]{36})") {
            powercfg /setactive $Matches[1]
        } else {
            # Duplicate balanced plan as High Performance
            powercfg /duplicatescheme 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
            powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
        }
        Write-Ok "Power plan set to High Performance"
    } catch {
        Write-Warn "Could not set power plan: $_"
    }

    # Disable sleep and hibernate
    powercfg /change standby-timeout-ac 0
    powercfg /change standby-timeout-dc 0
    powercfg /change monitor-timeout-ac 0
    powercfg /change hibernate-timeout-ac 0
    powercfg /hibernate off 2>&1 | Out-Null
    Write-Ok "Sleep and hibernate disabled"

    # Disable Windows Update auto-restart
    try {
        $regPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
        if (-not (Test-Path $regPath)) { New-Item -Path $regPath -Force | Out-Null }
        Set-ItemProperty -Path $regPath -Name "NoAutoRebootWithLoggedOnUsers" -Value 1 -Type DWord
        Set-ItemProperty -Path $regPath -Name "AUOptions" -Value 2 -Type DWord  # Notify before download
        Write-Ok "Windows Update auto-restart disabled"
    } catch {
        Write-Warn "Could not configure Windows Update: $_"
    }

    # Optional: Configure auto-login
    if (-not $SkipAutoLogin) {
        Write-Host ""
        $configAutoLogin = Read-Host "  Configure auto-login for this VM? (y/N)"
        if ($configAutoLogin -eq 'y' -or $configAutoLogin -eq 'Y') {
            $autoUser = Read-Host "  Username for auto-login"
            $autoPass = Read-Host "  Password for auto-login" -AsSecureString
            $autoPassPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                [Runtime.InteropServices.Marshal]::SecureStringToBSTR($autoPass))

            $regPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
            Set-ItemProperty -Path $regPath -Name "AutoAdminLogon" -Value "1"
            Set-ItemProperty -Path $regPath -Name "DefaultUserName" -Value $autoUser
            Set-ItemProperty -Path $regPath -Name "DefaultPassword" -Value $autoPassPlain
            Write-Ok "Auto-login configured for user: $autoUser"
        } else {
            Write-Info "Auto-login skipped"
        }
    }
}

# ─── PHASE 9: CONFIGURE FIREWALL ────────────────────────────────────────────────
function Set-FirewallRules {
    Write-Step "Configuring Windows Firewall..."

    $rules = @(
        @{ Name = "ApplyPilot-Dashboard"; Port = 5173; Description = "ApplyPilot Frontend (Vite)" }
        @{ Name = "ApplyPilot-API";       Port = 8000; Description = "ApplyPilot Backend API" }
    )

    foreach ($rule in $rules) {
        $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
        if ($existing) {
            Remove-NetFirewallRule -DisplayName $rule.Name
        }

        New-NetFirewallRule `
            -DisplayName $rule.Name `
            -Direction Inbound `
            -Protocol TCP `
            -LocalPort $rule.Port `
            -Action Allow `
            -Profile Domain,Private `
            -Description $rule.Description | Out-Null

        Write-Ok "Firewall rule: $($rule.Name) (TCP $($rule.Port)) — allowed on Private/Domain"
    }
}

# ─── PHASE 10: VERIFICATION ─────────────────────────────────────────────────────
function Test-Installation {
    Write-Step "Running verification health check..."

    # Start the service task
    Write-Info "Starting ApplyPilot service..."
    try {
        Start-ScheduledTask -TaskName "ApplyPilot-Service" -ErrorAction SilentlyContinue
    } catch {
        Write-Warn "Could not auto-start service task. You may need to start manually."
    }

    # Wait for startup
    Write-Info "Waiting 15 seconds for service to initialize..."
    for ($i = 1; $i -le 15; $i++) {
        Write-Progress -Activity "Waiting for service" -Status "$i/15 seconds" -PercentComplete ([int]($i / 15 * 100))
        Start-Sleep -Seconds 1
    }
    Write-Progress -Activity "Waiting for service" -Completed

    # Health check
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/stats" -UseBasicParsing -TimeoutSec 10
        if ($response.StatusCode -eq 200) {
            Write-Ok "Backend API is responding (HTTP 200)"
        } else {
            Write-Warn "Backend returned HTTP $($response.StatusCode)"
        }
    } catch {
        Write-Warn "Backend not responding yet. It may need more time to start."
        Write-Info "Try: Invoke-WebRequest http://localhost:8000/api/stats"
    }

    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 10
        if ($response.StatusCode -eq 200) {
            Write-Ok "Dashboard is responding (HTTP 200)"
        }
    } catch {
        Write-Warn "Dashboard not responding yet. Check if frontend started."
    }
}

# ─── PHASE 11: PRINT SUMMARY ────────────────────────────────────────────────────
function Show-Summary {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.PrefixOrigin -eq "Dhcp" } | Select-Object -First 1).IPAddress
    if (-not $ip) { $ip = "localhost" }

    $summary = @"

    ╔═══════════════════════════════════════════════════════════╗
    ║              ✔ SETUP COMPLETE                             ║
    ╠═══════════════════════════════════════════════════════════╣
    ║                                                           ║
    ║  Installed:                                               ║
    ║    • Git, Python 3.11, Node.js LTS                       ║
    ║    • Playwright Chromium (stealth browser)                ║
    ║    • Python dependencies + Node dependencies             ║
    ║                                                           ║
    ║  Services Registered:                                     ║
    ║    • ApplyPilot-Service    (starts on login)             ║
    ║    • ApplyPilot-Watchdog   (health check every 5 min)   ║
    ║    • ApplyPilot-WeeklyReboot (Sunday 3:00 AM)           ║
    ║                                                           ║
    ║  System Configured:                                       ║
    ║    • High Performance power plan                         ║
    ║    • Sleep/Hibernate disabled                            ║
    ║    • Windows Update auto-restart blocked                 ║
    ║    • Firewall: ports 5173, 8000 open (private network)  ║
    ║                                                           ║
    ║  Access Dashboard:                                        ║
    ║    Local:   http://localhost:5173                         ║
    ║    Network: http://${ip}:5173                             ║
    ║                                                           ║
    ║  Install Path: $InstallPath                     ║
    ║                                                           ║
    ║  Next Steps:                                              ║
    ║    1. Open dashboard → Settings → verify config          ║
    ║    2. Agent Control → Dry Run ON → Start                 ║
    ║    3. Happy? Turn Dry Run OFF and apply!                 ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝

"@
    Write-Host $summary -ForegroundColor Cyan
    Write-Host "  Need help? https://github.com/rahgoel2510/applypilot" -ForegroundColor Gray
    Write-Host ""
}

# ═══════════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════════

$startTime = Get-Date
Show-Banner

Write-Host "  Install path: $InstallPath" -ForegroundColor Gray
Write-Host "  Started at:   $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""

try {
    Assert-Prerequisites
    Install-Chocolatey
    Install-Software
    Install-Repository
    Install-ProjectDeps
    Set-Environment
    Register-Services
    Set-AlwaysOn
    Set-FirewallRules
    Test-Installation
    Show-Summary

    $elapsed = (Get-Date) - $startTime
    Write-Host "  Total time: $([math]::Round($elapsed.TotalMinutes, 1)) minutes" -ForegroundColor Gray
    Write-Host ""
} catch {
    Write-Host "`n" -NoNewline
    Write-Err "Setup failed: $_"
    Write-Err "Stack trace: $($_.ScriptStackTrace)"
    Write-Host ""
    Write-Info "Please fix the error above and re-run this script. It's safe to re-run."
    exit 1
}

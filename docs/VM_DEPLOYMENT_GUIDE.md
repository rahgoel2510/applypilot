# ApplyPilot — Windows VM Production Deployment Guide

**Target:** Fresh Windows 10/11 VM (Azure, AWS EC2, GCP, Hetzner, or local Hyper-V)  
**Goal:** Secure, always-on, self-healing deployment with hardening from the Architecture Review

---

## App State After Each Phase

| Phase | What You Get | Security | Can Deploy? |
|-------|-------------|----------|-------------|
| **Phase 0** (Emergency fixes) | Auth on API, CORS locked, secrets rotated | Basic protection | ✅ Yes — minimum viable secure |
| **Phase 1** (Security hardening) | Rate limiting, encrypted secrets, container hardening | Production-grade single-user | ✅ Yes — recommended for personal VM |
| **Phase 2** (Privacy) | Data retention, GDPR compliance, encrypted DB | Compliant self-hosted | ✅ Yes — safe for EU users |
| **Phase 3** (Scalability) | PostgreSQL, Redis, structured logs, metrics | Observable & resilient | ✅ Yes — ready for growth |
| **Phase 4** (Multi-tenancy) | Multi-user, RBAC, isolated agents | Full SaaS | ✅ Yes — can serve others |

**For your use case (personal VM, single user):** You need Phase 0 + Phase 1 minimum. That's ~2 weeks of work.

---

## What You Can Deploy TODAY (As-Is)

Your `setup-vm.ps1` script already handles fresh VM deployment end-to-end. It works, but exposes the app without authentication. Here's the risk profile:

| ✅ Works | ⚠️ Risk |
|----------|---------|
| Auto-installs everything via Chocolatey | API has zero auth (anyone on network can control) |
| Registers as Windows service (auto-start on login) | Secrets readable by any local process |
| Watchdog restarts on crash | No TLS (HTTP only) |
| Weekly reboot for cleanup | No rate limiting on API |
| Firewall rules for ports 5173/8000 | CORS allows all origins |

**Bottom line:** It's deployable TODAY if the VM is on a private network with no inbound internet access. If the VM has a public IP, you MUST complete Phase 0 first.

---

## Secure Deployment Architecture (Recommended)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Windows VM (Fresh)                            │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Caddy Reverse Proxy (auto-TLS, auth, rate limiting)      │   │
│  │  :443 → localhost:8000 (API)                              │   │
│  │  :443/app → localhost:5173 (Dashboard)                    │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                          │                                        │
│  ┌──────────────────────▼───────────────────────────────────┐   │
│  │  FastAPI Backend (:8000, localhost only)                    │   │
│  │  + Basic Auth middleware (API key or JWT)                  │   │
│  │  + CORS restricted to your domain                         │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                          │                                        │
│  ┌──────────────────────▼───────────────────────┐               │
│  │  LinkedIn Agent (background process)          │               │
│  │  + Browser session in encrypted user profile  │               │
│  └───────────────────────────────────────────────┘               │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Data (all in C:\ApplyPilot\data\)                          │ │
│  │  • tracker.db (SQLite + WAL mode)                           │ │
│  │  • browser_data/ (LinkedIn session)                         │ │
│  │  • resumes/ (encrypted at rest)                             │ │
│  │  • logs/ (rotating, 30-day retention)                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Windows Services:                                                │
│  • ApplyPilot-Service (auto-start on login)                      │
│  • ApplyPilot-Watchdog (health check every 5 min)                │
│  • ApplyPilot-Caddy (reverse proxy)                              │
│  • ApplyPilot-WeeklyReboot (Sunday 3 AM)                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step: Fresh Windows VM Deployment

### Prerequisites

- Windows 10/11 VM (2+ vCPU, 4GB+ RAM, 30GB+ disk)
- RDP access to the VM
- Your `.env` credentials ready (LinkedIn, Telegram, OpenRouter)

### Option A: One-Click (Current — works but insecure for public VMs)

```powershell
# RDP into your VM, open PowerShell as Admin, then:
Set-ExecutionPolicy Bypass -Scope Process -Force
iwr -useb https://raw.githubusercontent.com/rahgoel2510/applypilot/main/setup-vm.ps1 | iex
```

This runs the existing `setup-vm.ps1` which:
1. Installs Chocolatey → Git, Python 3.11, Node.js
2. Clones repo to `C:\ApplyPilot`
3. Creates venv, installs deps, Playwright Chromium
4. Prompts for credentials → writes `.env`
5. Registers Windows scheduled tasks (service + watchdog + weekly reboot)
6. Configures power plan (no sleep), firewall rules
7. Starts the service and verifies health

### Option B: Hardened Deployment (Recommended)

After Option A completes, apply these hardening steps:

#### Step 1: Lock Down the API (5 minutes)

Create `C:\ApplyPilot\tracker\backend\auth_middleware.py`:

```python
"""Minimal API key auth — apply BEFORE going public."""
import os
import secrets
from fastapi import Request, HTTPException

API_KEY = os.environ.get("APPLYPILOT_API_KEY", "")

# Generate a key if none exists
if not API_KEY:
    API_KEY = secrets.token_urlsafe(32)
    print(f"\n  ⚠️  Generated API key (add to .env): APPLYPILOT_API_KEY={API_KEY}\n")

EXEMPT_PATHS = {"/api/stats", "/api/health", "/docs", "/openapi.json"}

async def verify_api_key(request: Request, call_next):
    if request.url.path in EXEMPT_PATHS:
        return await call_next(request)
    if request.url.path.startswith("/ws"):
        # WebSocket auth via query param
        token = request.query_params.get("token", "")
        if token != API_KEY:
            raise HTTPException(403, "Invalid token")
        return await call_next(request)
    
    auth = request.headers.get("X-API-Key", "")
    if auth != API_KEY:
        raise HTTPException(401, "Unauthorized")
    return await call_next(request)
```

Then in `main.py`, add after the app is created:
```python
from auth_middleware import verify_api_key
app.middleware("http")(verify_api_key)
```

#### Step 2: Fix CORS (2 minutes)

In `main.py`, change:
```python
allow_origins=["*"]  # ← REMOVE THIS
```
To:
```python
allow_origins=["http://localhost:5173", "https://your-domain.com"]
allow_credentials=False  # ← Change to False
```

#### Step 3: Remove the `/api/settings/env` Endpoint (2 minutes)

In `settings_routes.py`, delete or comment out the `/env` endpoint. Instead, pass env vars directly to the agent subprocess from the `.env` file.

#### Step 4: Install Caddy as Reverse Proxy (10 minutes)

```powershell
choco install caddy -y

# Create Caddyfile
@"
your-vm-ip.nip.io {
    reverse_proxy localhost:8000
    basicauth * {
        admin $2a$14$YOUR_BCRYPT_HASH_HERE
    }
    rate_limit {
        zone dynamic_zone {
            key {remote_host}
            events 100
            window 1m
        }
    }
}
"@ | Set-Content C:\Caddy\Caddyfile

# Register as service
caddy run --config C:\Caddy\Caddyfile
```

#### Step 5: Restrict Firewall (2 minutes)

```powershell
# Remove the open rules from setup-vm.ps1
Remove-NetFirewallRule -DisplayName "ApplyPilot-Dashboard"
Remove-NetFirewallRule -DisplayName "ApplyPilot-API"

# Only allow Caddy's HTTPS port
New-NetFirewallRule -DisplayName "ApplyPilot-HTTPS" `
    -Direction Inbound -Protocol TCP -LocalPort 443 `
    -Action Allow -Profile Any

# Block direct access to backend ports from outside
New-NetFirewallRule -DisplayName "ApplyPilot-Block-8000" `
    -Direction Inbound -Protocol TCP -LocalPort 8000 `
    -Action Block -Profile Public
```

#### Step 6: Enable SQLite WAL Mode (1 minute)

Add to `database.py` after engine creation:
```python
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
```

---

## VM Provider Recommendations

| Provider | Spec | Monthly Cost | Notes |
|----------|------|-------------|-------|
| **Hetzner Cloud** (CX21) | 2 vCPU, 4GB, 40GB | ~€5.80 | Best value, EU data residency |
| **AWS EC2** (t3.small) | 2 vCPU, 2GB, 30GB | ~$15-20 | Use spot for ~$5 |
| **Azure** (B2s) | 2 vCPU, 4GB, 30GB | ~$15 | Good Windows support |
| **Oracle Cloud** (Always Free) | 1 vCPU, 1GB | FREE | Tight on RAM for Chromium |
| **Local Hyper-V** | Whatever you assign | $0 | Best for home use |

**Minimum specs:** 2 vCPU, 4GB RAM (Chromium needs 1-2GB alone), 20GB disk.

---

## Post-Deployment Checklist

```
□ VM is running and accessible via RDP
□ ApplyPilot service is registered and auto-starts
□ Watchdog task runs every 5 minutes  
□ Dashboard accessible at https://your-domain (or http://vm-ip:5173 for private network)
□ .env credentials are correct (test with dry-run first)
□ LinkedIn session is active (login manually once in browser)
□ Telegram bot responds to /ping
□ Firewall blocks direct access to ports 8000/5173 (Caddy handles external)
□ API key is set in .env and frontend uses it
□ Weekly reboot task is registered (Sunday 3 AM)
□ Logs rotating and accessible via service.ps1 logs
```

---

## Monitoring Your VM Deployment

### Health Check Script (run via Telegram /status)

The watchdog already checks `http://localhost:8000/api/stats`. To add Telegram alerting when it's down:

```powershell
# Add to watchdog.ps1:
$TelegramToken = $env:TELEGRAM_BOT_TOKEN
$ChatId = $env:TELEGRAM_CHAT_ID

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/stats" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -ne 200) { throw "Unhealthy" }
} catch {
    # Alert via Telegram
    $msg = "⚠️ ApplyPilot is DOWN on $(hostname). Attempting restart..."
    Invoke-RestMethod -Uri "https://api.telegram.org/bot$TelegramToken/sendMessage" `
        -Method Post -Body @{ chat_id = $ChatId; text = $msg } -ErrorAction SilentlyContinue
    
    # Restart
    Start-ScheduledTask -TaskName "ApplyPilot-Service"
}
```

### Disk Space Alert

```powershell
# Add as a daily task
$freeGB = [math]::Round((Get-PSDrive C).Free / 1GB, 1)
if ($freeGB -lt 5) {
    $msg = "⚠️ ApplyPilot VM low disk: ${freeGB}GB free"
    # Send Telegram alert...
}
```

---

## Upgrading Your Deployment

```powershell
# SSH/RDP into VM, then:
cd C:\ApplyPilot
git pull
.\.venv\Scripts\pip.exe install -r requirements.txt --quiet
cd tracker\frontend && npm install --silent && cd ..\..

# Restart service
pwsh ./service.ps1 stop
pwsh ./service.ps1 start
```

---

## Summary: What to Do Right Now

1. **Your existing `setup-vm.ps1` works perfectly for a fresh VM** — it's already a one-click deployment
2. **Add the 6 hardening steps above** (30 minutes total) before exposing to the internet
3. **Keep it on a private network** if you skip hardening — it's safe as a localhost-only tool
4. **Phase 0 fixes are the minimum** before any public exposure

The app is fully functional for personal use today. The architecture review gaps matter when you want to:
- Expose it publicly (security)
- Run it for multiple people (multi-tenancy)
- Handle EU users' data (GDPR)
- Scale beyond one LinkedIn account (scalability)

For a single user on a private VM, Phases 0 + 1 give you a rock-solid, always-on deployment.

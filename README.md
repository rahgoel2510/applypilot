<p align="center">
  <img src="docs/banner.png" alt="ApplyPilot" width="600" />
</p>

<h1 align="center">ApplyPilot</h1>
<p align="center"><strong>Autonomous LinkedIn Job Application Agent</strong></p>
<p align="center"><em>Powered by Rahul</em></p>

<!-- Badges row -->
<p align="center">
  <a href="https://hub.docker.com/r/rahgoel2510/applypilot"><img src="https://img.shields.io/docker/pulls/rahgoel2510/applypilot?style=flat-square&labelColor=black" alt="Docker Pulls" /></a>
  <a href="https://github.com/rahgoel2510/applypilot/releases/latest"><img src="https://img.shields.io/github/v/release/rahgoel2510/applypilot?style=flat-square&labelColor=black" alt="GitHub Release" /></a>
  <a href="https://github.com/rahgoel2510/applypilot/blob/main/LICENSE"><img src="https://img.shields.io/github/license/rahgoel2510/applypilot?style=flat-square&labelColor=black" alt="License" /></a>
  <a href="https://github.com/rahgoel2510/applypilot/stargazers"><img src="https://img.shields.io/github/stars/rahgoel2510/applypilot?style=flat-square&labelColor=black" alt="Stars" /></a>
  <a href="https://github.com/rahgoel2510/applypilot/commits/main"><img src="https://img.shields.io/github/last-commit/rahgoel2510/applypilot?style=flat-square&labelColor=black" alt="Last Commit" /></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="https://rahgoel2510.github.io/applypilot">Website</a> •
  <a href="docs/GUIDE.md">Full Guide</a> •
  <a href="#features">Features</a> •
  <a href="https://ko-fi.com/goelrah">Ko-fi</a>
</p>

---

**ApplyPilot** is a fully autonomous agent that scans LinkedIn for jobs matching your profile, scores them for relevance, and applies on your behalf using Easy Apply — all while keeping you in the loop for sensitive decisions. It ships with a professional admin dashboard, self-learning scoring, and runs as a background service on any platform.

## 🚀 Features

### Agent Intelligence
- 🔍 **Auto-Scan** — Monitors LinkedIn for jobs matching your keywords, locations, and saved searches.
- 📊 **Match Scoring** — Uses LinkedIn Premium match percentage to rank jobs by fit.
- ⚡ **Easy Apply Automation** — Fills and submits multi-step Easy Apply forms end-to-end.
- 🧑‍💼 **Human-in-the-Loop** — Pauses for sensitive fields (CTC, notice period, visa) and asks you via Telegram.
- 🧠 **Self-Learning** — Learns from your actions (promoting/rejecting jobs on the board) to improve future scoring.
- 🗂️ **Cloud Dedup** — Tracks every job ever seen across all your machines via Turso cloud DB.
- ✉️ **InMail Drafting** — AI-generated personalized cold outreach stored per-job for review.

### Dashboard (Material UI Admin)
- 📈 **D3.js Charts** — Animated funnel chart, interactive score donut, sparkline trends.
- 📋 **Kanban Board** — Drag-and-drop columns (Discovered → Applied → Interview → Offer). Click any card for detailed modal with timeline, score analysis, and LinkedIn link.
- 🤖 **Agent Control** — Start/stop, dry-run toggle, match threshold slider, live terminal output, run history.
- ⏰ **Visual Scheduler** — Configure run frequency (interval or specific times), active hours, days of week. No cron expressions needed.
- 🔧 **Settings** — All config editable in the UI (LinkedIn, Telegram, AI model, search keywords, thresholds).
- 🌓 **Dark/Light Mode** — System preference detection with manual toggle.

### Notifications
- 📬 **Rich Telegram Alerts** — Per-job notifications with clickable LinkedIn URL, score %, company, location.
- 📊 **Full Funnel Report** — After each scan: total found → deduped → discovered → applied → skipped → errors.
- ⏸️ **Human Input Requests** — Telegram prompts when the agent needs your input on sensitive fields.

### Infrastructure
- 🖥️ **Background Service** — Runs persistently via launchd (macOS), systemd (Linux), or Task Scheduler (Windows).
- 🐳 **Docker Deploy** — Single `docker compose up` with health checks and auto-restart.
- 🔒 **Environment Isolation** — Each machine gets its own tracker DB + cloud dedup DB (Turso).
- 🧪 **Dry-Run Mode** — Preview what the agent would do without submitting any applications.

## 📦 Quick Start

### Local Setup (Recommended)

**macOS / Linux:**
```bash
git clone https://github.com/rahgoel2510/applypilot.git
cd applypilot
bash setup.sh        # Installs Python, Node, Chromium, all deps
bash start.sh        # Starts backend + frontend
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/rahgoel2510/applypilot.git
cd applypilot
pwsh ./setup.ps1     # Installs Python venv, deps, Playwright, Node
pwsh ./start.ps1     # Starts backend + frontend, opens browser
```

Dashboard opens at **http://localhost:5173**

### Docker Setup

```bash
bash docker-setup.sh       # macOS/Linux
pwsh ./docker-setup.ps1    # Windows
```

This builds the image, starts the container, runs health checks, and opens **http://localhost:80**.

### Run as Background Service

```bash
# macOS/Linux
bash service.sh install    # Auto-starts on login, restarts on crash

# Windows
pwsh ./service.ps1 install # Same — uses Task Scheduler
```

Service commands: `install | start | stop | status | logs | uninstall`

## 🖥️ Dashboard Pages

| Page | Description |
|------|-------------|
| **Dashboard** | KPI cards (Total Jobs, Applied, Match Rate, Pipeline), D3 funnel chart, score distribution donut, recent activity, jobs table, top companies. |
| **Agent Control** | Status indicator, Start/Stop buttons, mode toggle (Single/Daemon), dry-run switch, threshold/limit config. Tabs: Pipeline visualization, Live terminal output, Run history with expandable details. |
| **Board** | Kanban with 7 columns. Drag cards between stages. Hover for tooltip (score, stage, date). Click for detailed modal (score gauge, agent analysis, timeline, LinkedIn link, notes). |
| **Scheduler** | Fixed interval or custom schedule (specific times picker). Active hours, days of week, next runs preview. |
| **Agents** | Enable/disable individual agent modules (Scanner, Applicant, InMail Drafter, Telegram Notifier). |
| **Settings** | All configuration in one place: LinkedIn, AI model, Telegram, search keywords, locations, thresholds, candidate info, InMail settings. |
| **Service** | Background daemon status, start/stop/restart, auto-start on boot toggle, uptime chart. |

## 🔄 Agent Pipeline

Each scan follows these 5 stages:

```
1. STARTUP       → Load config → Launch browser → Verify LinkedIn session
2. DISCOVER      → Scan recommended → Keyword search → Custom URLs
3. EVALUATE      → Dedup check → External apply? → Get match score → Meets threshold?
4. ACT           → Draft InMail → Submit Easy Apply → Handle human input → Save to DB
5. WRAP UP       → Telegram alert → Sync dedup → Generate report
```

Jobs that don't pass evaluation are tracked with their score for audit.

## ⚙️ Configuration

All settings are configurable via the dashboard UI (Settings page) or via `config.yaml`:

```yaml
linkedin:
  email: your-email@example.com
  password: ${LINKEDIN_PASSWORD}

search:
  keywords: ["Software Engineer", "Backend Developer"]
  locations: ["Bengaluru", "Remote"]
  posted_within: "24h"
  match_threshold: 0.70
  max_postings_per_run: 25
  skip_external_apply: true

candidate:
  name: "Your Name"
  email: "you@example.com"
  phone: "+91-XXXXXXXXXX"
  notice_period: "30 days"
  willing_to_relocate: true

notifications:
  telegram:
    bot_token: ${TELEGRAM_BOT_TOKEN}
    chat_id: ${TELEGRAM_CHAT_ID}
    notify_on_submit: true

inmail:
  enabled: true

scheduler:
  interval_minutes: 60
  active_hours_start: 9
  active_hours_end: 18
```

## 🔒 Safety & Privacy

- **100% Self-Hosted** — Credentials and data never leave your machine.
- **Human-in-the-Loop** — Never guesses sensitive fields. Pauses and asks via Telegram.
- **No Telemetry** — Zero analytics, zero outbound calls except to LinkedIn and your Telegram bot.
- **Dry-Run by Default** — Verify behavior before going live.
- **Open Source** — Fully auditable code.
- **Environment Isolation** — Each machine has its own DB. Cloud dedup uses per-environment Turso tokens.

## 📂 Project Structure

```
applypilot/
├── linkedin_agent/          # Agent core
│   ├── orchestrator.py      # Main pipeline (5 stages)
│   ├── browser.py           # Playwright browser automation
│   ├── matcher.py           # Score evaluation + self-learning
│   ├── applicant.py         # Easy Apply form filler
│   ├── telegram_bot.py      # Rich notifications + human input
│   ├── inmail.py            # AI-powered InMail drafting
│   ├── dedup_db.py          # Cloud dedup (Turso/SQLite)
│   └── tracker_client.py    # Pushes events to tracker API
├── tracker/
│   ├── backend/             # FastAPI + SQLAlchemy
│   │   ├── main.py          # App entry + routers
│   │   ├── models.py        # Job, InMailDraft, FeedbackSignal
│   │   ├── routes.py        # CRUD + webhook + audit
│   │   ├── scheduler_routes.py
│   │   ├── service_routes.py
│   │   └── agents_routes.py
│   └── frontend/            # React 19 + MUI + D3.js
│       └── src/
│           ├── pages/       # Dashboard, AgentControl, Board, etc.
│           ├── components/  # D3Charts, AgentPipelineView
│           ├── layout/      # AppLayout (sidebar + topbar)
│           └── theme.js     # AWS-inspired design system
├── setup.sh / setup.ps1     # First-time setup
├── start.sh / start.ps1     # Start app (foreground)
├── service.sh / service.ps1 # Background service management
├── docker-setup.sh / .ps1   # Docker build + test
├── docker-compose.yml       # Container orchestration
└── config.yaml              # Agent configuration
```

## 🛠️ Development

```bash
# Clone
git clone https://github.com/rahgoel2510/applypilot.git
cd applypilot

# Setup
bash setup.sh

# Run in dev mode
bash start.sh

# Run tests
source .venv/bin/activate
pytest tests/ -v

# Build frontend for production
cd tracker/frontend && npm run build
```

**Requirements:** Python 3.11+, Node.js 18+, Chrome/Chromium.

## 🧠 Self-Learning

The agent improves over time based on your actions:
- Move a job to "Interviewing" → positive signal for that company
- Reject a job → negative signal
- After enough feedback, the agent boosts/penalizes scores for specific companies by ±10%
- Calibration warnings if your threshold diverges from actual interview outcomes

View feedback data: `GET /api/feedback/summary`

## 👨‍💻 Author

<p align="center">
  <strong>Powered by Rahul</strong><br/>
  <a href="https://github.com/rahgoel2510">GitHub</a> •
  <a href="https://rahgoel2510.github.io/applypilot">Website</a> •
  <a href="https://www.linkedin.com/in/rahulgoel2510">LinkedIn</a>
</p>

## ☕ Support

If ApplyPilot saved you time or landed you a job, consider buying me a coffee!

<p align="center">
  <a href="https://ko-fi.com/goelrah">
    <img src="https://img.shields.io/badge/Ko--fi-Support%20ApplyPilot-ff5e5b?style=flat-square&logo=ko-fi&labelColor=black" alt="Ko-fi" />
  </a>
</p>

## 📄 License

[MIT](LICENSE) © Rahul

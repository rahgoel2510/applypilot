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
- 📊 **Dual Scoring** — Uses LinkedIn Premium match percentage (primary) with automatic **fallback keyword scoring** when Premium is unavailable.
- ⚡ **Easy Apply Automation** — Fills and submits multi-step Easy Apply forms end-to-end.
- 🧑‍💼 **Human-in-the-Loop** — Pauses for sensitive fields, asks via Telegram, fills your answers, and **resumes the application automatically**.
- 🧠 **Self-Learning** — Learns from your actions + seeded target/blocklist companies to boost/penalize scores from day 1.
- 🗂️ **Cloud Dedup** — Tracks every job ever seen across all your machines via Turso cloud DB.
- ✉️ **InMail Drafting** — AI-generated personalized cold outreach sent **after** confirmed application.
- 🤖 **AI Answer Generation** — Uses LLM to write contextual answers for cover letters and "why this company" questions.
- 🔄 **Retry Queue** — Failed applications are automatically retried with exponential backoff (5→15→45 min).
- 🛡️ **Anti-Detection** — Stealth browser automation with rotating user-agents, JS injection, and challenge detection.
- 📄 **Multi-Resume** — Keyword-to-resume mapping: EM roles get one resume, TPM roles get another.
- ⚡ **Urgent Mode** — First-week sprint: 30-min intervals, 100 jobs/run, auto-disables after 7 days.

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
- 🔗 **External Job Alerts** — External apply jobs sent to Telegram with direct link for manual application.

### Safety & Reliability
- 🛡️ **Stealth Mode** — 12 rotating user-agents, 28 anti-detection Chromium args, stealth JS injection, session health monitoring.
- 🚨 **Challenge Recovery** — Detects CAPTCHAs/security checks, takes screenshot, sends Telegram alert, waits 5 min for manual resolution.
- 📊 **Daily Application Cap** — Tracks daily submissions (default 80/day) to avoid LinkedIn rate limiting. Auto-stops and notifies.
- ✅ **Already-Applied Detection** — Detects LinkedIn's "Applied" badge to skip re-application attempts.
- 🔄 **Retry with Backoff** — Failed applications retried automatically (3 attempts, exponential backoff).
- 📋 **Response Tracking** — Periodically checks LinkedIn's "My Jobs → Applied" for status updates (viewed, downloaded, closed).

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

Each scan follows these stages:

```
1. STARTUP       → Load config → Launch stealth browser → Verify LinkedIn session
                   ↳ Challenge detected? → Screenshot + Telegram alert → Wait 5 min
2. DISCOVER      → Scan recommended → Keyword×Location search (OR queries) → Custom URLs
                   ↳ Urgent mode: 100 jobs/run | Normal: 50 jobs/run
                   ↳ First run: scans past week | Subsequent: past 24h
3. EVALUATE      → Dedup check → Already applied? → External apply? → Get match score
                   ↳ No Premium? → Fallback keyword scoring
                   ↳ Self-learning: target companies +15%, blocklist -20%
                   ↳ Daily cap check (80/day default)
4. ACT           → Select resume (per job title) → Submit Easy Apply → Handle questions
                   ↳ Pre-configured answers for known sensitive fields
                   ↳ AI-generated answers for cover letters / "why this company"
                   ↳ Human-in-the-loop for truly unknown fields (5 min timeout)
                   ↳ Failed? → Add to retry queue (3 attempts, exponential backoff)
5. WRAP UP       → Telegram alert → InMail draft (post-submission) → Sync dedup
                   ↳ Check application response statuses (viewed/rejected)
                   ↳ Process retry queue → Generate report
```

Jobs that don't pass evaluation are tracked with their score for audit.

## ⚙️ Configuration

All settings are configurable via the dashboard UI (Settings page) or via `config.yaml`:

```yaml
candidate:
  name: "Your Name"
  email: "you@example.com"
  phone: "+91-XXXXXXXXXX"
  resume_filename: "resume.pdf"
  notice_period: "30 days"
  willing_to_relocate: true
  skills:
    - "engineering management"
    - "system design"
    - "agile"
  resume_mapping:
    - keywords: ["Engineering Manager", "Director of Engineering"]
      resume: "EM_Resume.pdf"
    - keywords: ["Technical Program Manager", "TPM"]
      resume: "TPM_Resume.pdf"
  sensitive_field_answers:
    salary_expectation: "As per company standards"
    current_ctc: "Confidential - happy to discuss"
    years_of_experience: "12"
  human_input_timeout: 300

search:
  keywords: ["Software Engineer", "Backend Developer"]
  locations: ["Bengaluru", "Remote", "India"]
  posted_within: "24h"
  initial_scan_window: "week"
  match_threshold: 0.70
  max_postings_per_run: 50
  skip_external_apply: false
  track_external_apply: true
  fallback_scoring: true
  daily_application_limit: 80

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
  urgent_mode: true
  urgent_interval_minutes: 30
  urgent_max_postings: 100
  urgent_duration_days: 7

self_learning:
  target_companies: ["Google", "Microsoft", "Amazon"]
  blocklist_companies: ["Wipro", "Infosys", "TCS"]
  target_boost: 0.15
  blocklist_penalty: 0.20
```

## 🔒 Safety & Privacy

- **100% Self-Hosted** — Credentials and data never leave your machine.
- **Human-in-the-Loop** — Never guesses sensitive fields. Pauses and asks via Telegram.
- **No Telemetry** — Zero analytics, zero outbound calls except to LinkedIn and your Telegram bot.
- **Dry-Run by Default** — Verify behavior before going live.
- **Daily Cap Protection** — Stops at 80 applications/day to prevent LinkedIn account restrictions.
- **Anti-Detection** — Stealth browser mode with rotating fingerprints to avoid bot detection.
- **Open Source** — Fully auditable code.
- **Environment Isolation** — Each machine has its own DB. Cloud dedup uses per-environment Turso tokens.

## 📂 Project Structure

```
applypilot/
├── linkedin_agent/              # Agent core
│   ├── orchestrator.py          # Main pipeline (5 stages)
│   ├── browser.py               # Playwright browser automation + stealth
│   ├── stealth.py               # Anti-detection: rotating UAs, JS injection, Chromium args
│   ├── matcher.py               # Score evaluation + self-learning + target/blocklist
│   ├── fallback_scorer.py       # Keyword-based scoring without Premium
│   ├── applicant.py             # Easy Apply form filler + human-in-the-loop
│   ├── answer_generator.py      # AI-generated answers for cover letters/questions
│   ├── telegram_bot.py          # Rich notifications + human input collection
│   ├── inmail.py                # AI-powered InMail drafting
│   ├── dedup_db.py              # Cloud dedup (Turso/SQLite)
│   ├── tracker_client.py        # Pushes events to tracker API
│   ├── retry_queue.py           # Exponential backoff retry for failed applications
│   ├── daily_cap.py             # Daily application limit tracking
│   ├── config.py                # Typed settings (YAML + env)
│   ├── scheduler.py             # Background scheduling + service management
│   ├── smart_parser.py          # LLM-assisted page parsing
│   ├── logger.py                # Structured logging + CSV export
│   └── bot.py                   # Telegram command bot (/run, /status, /logs)
├── tracker/
│   ├── backend/                 # FastAPI + SQLAlchemy
│   │   ├── main.py              # App entry + routers
│   │   ├── models.py            # Job, InMailDraft, FeedbackSignal
│   │   ├── routes.py            # CRUD + webhook + audit
│   │   ├── auto_repair.py       # LLM-based error diagnosis
│   │   ├── scheduler_routes.py
│   │   ├── service_routes.py
│   │   └── agents_routes.py
│   └── frontend/                # React 19 + MUI + D3.js
│       └── src/
│           ├── pages/           # Dashboard, AgentControl, Board, etc.
│           ├── components/      # D3Charts, AgentPipelineView
│           ├── layout/          # AppLayout (sidebar + topbar)
│           └── theme.js         # AWS-inspired design system
├── tests/                       # pytest suite (125+ tests)
│   ├── test_config.py
│   ├── test_matcher.py
│   ├── test_orchestrator.py
│   ├── test_inmail.py
│   ├── test_fallback_scorer.py
│   ├── test_daily_cap.py
│   └── ...
├── setup.sh / setup.ps1         # First-time setup
├── start.sh / start.ps1         # Start app (foreground)
├── service.sh / service.ps1     # Background service management
├── docker-setup.sh / .ps1       # Docker build + test
├── docker-compose.yml           # Container orchestration
└── config.yaml                  # Agent configuration
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
python3 -m pytest tests/ -v

# Build frontend for production
cd tracker/frontend && npm run build
```

**Requirements:** Python 3.11+, Node.js 18+, Chrome/Chromium.

## 🧠 Self-Learning

The agent improves over time based on your actions:
- Move a job to "Interviewing" → positive signal for that company
- Reject a job → negative signal
- After enough feedback, the agent boosts/penalizes scores for specific companies by ±10%
- **Seeded from day 1**: Target companies get +15% boost, blocklist companies get -20% penalty
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

## 🏗️ Architecture: Event-Driven Pipeline

ApplyPilot uses a Kafka-inspired event bus for scalability and multi-platform support:

```
┌─────────────────┐     ┌────────────────────────────────┐     ┌─────────────┐
│  LinkedIn       │────▶│                                │────▶│  Evaluator  │
│  Adapter        │     │  Event Bus                     │     │  (scoring)  │
├─────────────────┤     │  ─────────────────────────     │     └──────┬──────┘
│  Indeed         │────▶│  Topics:                       │            │
│  Adapter (TBD)  │     │  • job.discovered              │     ┌──────▼──────┐
├─────────────────┤     │  • job.evaluated               │────▶│  Applicant  │
│  Naukri         │────▶│  • job.qualified               │     │  (submit)   │
│  Adapter (TBD)  │     │  • job.applied                 │     └──────┬──────┘
└─────────────────┘     │  • job.failed                  │            │
                        │  • job.external                │     ┌──────▼──────┐
                        │                                │────▶│  Notifier   │
                        │  Features:                     │     │  (Telegram) │
                        │  • Stage markers (audit trail) │     └─────────────┘
                        │  • Dead-letter queue (retry)   │
                        │  • Middleware (logging, dedup)  │
                        │  • Event persistence           │
                        └────────────────────────────────┘
```

**Key concepts:**
- **Events** carry all context + accumulate stage markers as they flow through the pipeline
- **Stages** are independent processors that subscribe to topics and produce new events
- **Platform Adapters** are discovery stages that produce `job.discovered` events
- **Dead-letter queue** captures failed events for retry (like Kafka DLQ)
- **Stage markers** = append-only log showing what happened at each stage (like consumer offsets)

Adding a new platform (e.g., Indeed) requires only implementing a `DiscoveryStage` subclass.

### Pipeline Runner (New)

```python
from linkedin_agent.pipeline import PipelineRunner

runner = PipelineRunner(dry_run=True)
await runner.setup()        # Browser, stages, middleware
await runner.run_cycle()    # CYCLE_STARTED → full pipeline flow
await runner.shutdown()     # Cleanup
```

### Adding a New Platform

```python
from linkedin_agent.pipeline import DiscoveryStage, JobEvent, EventType, Platform

class IndeedDiscoveryStage(DiscoveryStage):
    name = "indeed_discovery"

    async def discover_jobs(self, config) -> list[JobEvent]:
        # Your Indeed scraping logic here
        return [JobEvent(platform=Platform.INDEED, title="...", ...)]
```

Register it with the bus and it works — evaluation, application, and notifications are platform-agnostic.

## 📄 License

[MIT](LICENSE) © Rahul

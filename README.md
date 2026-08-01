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
  <a href="#setup-macos">macOS Setup</a> •
  <a href="#setup-windows">Windows Setup</a> •
  <a href="#setup-docker">Docker</a> •
  <a href="#configuration">Configure</a> •
  <a href="#usage">Usage</a> •
  <a href="https://ko-fi.com/goelrah">Ko-fi</a>
</p>

---

**ApplyPilot** scans LinkedIn for jobs matching your profile, scores them, and applies automatically using Easy Apply — while keeping you in the loop for sensitive decisions via Telegram. No LinkedIn Premium required.

## What It Does

1. **Scans** LinkedIn for jobs matching your keywords across multiple locations
2. **Scores** each job using LinkedIn's AI (or fallback keyword matching if no Premium)
3. **Applies** to qualifying jobs with your resume, pre-filled answers, and AI-generated cover letters
4. **Notifies** you via Telegram for every application, external link, or question it can't answer
5. **Learns** from your feedback to boost/penalize companies over time

Works without LinkedIn Premium. Works without Docker. Runs on macOS and Windows natively.

---

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| Python | 3.11+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| Git | Any | `git --version` |

That's it. No Docker needed. The setup script handles everything else (Chromium, pip packages, npm packages).

---

<h2 id="setup-macos">🍎 Setup — macOS / Linux</h2>

```bash
# 1. Clone
git clone https://github.com/rahgoel2510/applypilot.git
cd applypilot

# 2. Run setup (installs Python deps, Node deps, Playwright Chromium)
bash setup.sh

# 3. Configure your credentials
cp .env.example .env
nano .env   # Fill in your LinkedIn email/password and Telegram bot token
```

**`.env` file (required):**
```
LINKEDIN_EMAIL=your-email@gmail.com
LINKEDIN_PASSWORD=your-password
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789
OPENAI_API_KEY=sk-or-v1-your-openrouter-key
```

```bash
# 4. Start the app
bash start.sh
```

Opens **http://localhost:5173** — your dashboard.

**First time?** Go to Settings → configure your candidate info, keywords, and locations. Then go to Agent Control → click Start (with Dry Run ON) to test.

### Run as Background Service (auto-start on login)

```bash
bash service.sh install   # Installs and starts
bash service.sh status    # Check if running
bash service.sh logs      # View logs
bash service.sh stop      # Stop
bash service.sh uninstall # Remove completely
```

---

<h2 id="setup-windows">🪟 Setup — Windows (PowerShell)</h2>

Open PowerShell as Administrator:

```powershell
# 1. Clone
git clone https://github.com/rahgoel2510/applypilot.git
cd applypilot

# 2. Run setup (creates venv, installs deps, downloads Chromium)
pwsh ./setup.ps1

# 3. Configure credentials
Copy-Item .env.example .env
notepad .env   # Fill in LinkedIn, Telegram, and AI keys
```

**`.env` file (required):**
```
LINKEDIN_EMAIL=your-email@gmail.com
LINKEDIN_PASSWORD=your-password
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789
OPENAI_API_KEY=sk-or-v1-your-openrouter-key
```

```powershell
# 4. Start the app
pwsh ./start.ps1
```

Opens **http://localhost:5173** — your dashboard.

### Run as Background Service (Task Scheduler)

```powershell
pwsh ./service.ps1 install   # Auto-starts on login
pwsh ./service.ps1 status    # Check status
pwsh ./service.ps1 logs      # View logs
pwsh ./service.ps1 stop      # Stop
pwsh ./service.ps1 uninstall # Remove
```

---

<h2 id="setup-docker">🐳 Setup — Docker (Optional)</h2>

Only use Docker if you prefer containerized deployment. It's **not required**.

```bash
# macOS / Linux
bash docker-setup.sh

# Windows
pwsh ./docker-setup.ps1
```

This builds the image, starts the container, runs health checks, and opens **http://localhost:80**.

---

<h2 id="configuration">⚙️ Configuration</h2>

**All settings are configurable from the dashboard UI** — go to http://localhost:5173 → Settings.

The Settings page has tabs for: Candidate, Job Search, Scheduler, Self-Learning, Telegram, AI Model, InMail, and Advanced. Changes are saved to the database and applied automatically when the agent runs from the dashboard.

**For CLI usage**, the agent reads from `config.yaml` in the project root. Edit this file if you prefer running via command line:

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

job_search:
  keywords: ["Engineering Manager", "Technical Program Manager"]
  locations: ["India", "Bangalore", "Remote"]
  posted_within: "24h"
  initial_scan_window: "week"
  match_threshold: 0.70
  max_postings_per_run: 50
  skip_external_apply: false
  track_external_apply: true
  fallback_scoring: true
  daily_application_limit: 80

scheduler:
  interval_minutes: 60
  active_hours_start: 9
  active_hours_end: 22
  urgent_mode: true
  urgent_interval_minutes: 30
  urgent_max_postings: 100
  urgent_duration_days: 7

self_learning:
  target_companies: ["Google", "Microsoft", "Amazon"]
  blocklist_companies: ["Wipro", "Infosys", "TCS"]
  target_boost: 0.15
  blocklist_penalty: 0.20

inmail:
  enabled: true
  tone: "professional"
  max_length: 300
```

### Getting a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` → follow prompts → get your bot token
3. Message your new bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your chat_id
4. Add both to `.env`

### Getting an AI API Key (Free)

1. Go to [OpenRouter.ai](https://openrouter.ai/) → Sign up → Create API key
2. Free models are available (no credit card needed)
3. Add key to `.env` as `OPENAI_API_KEY`

---

<h2 id="usage">🚀 Usage</h2>

### From the Dashboard (Recommended)

1. Open **http://localhost:5173**
2. Go to **Agent Control**
3. Set: Mode = Single, Dry Run = ON, Threshold = 70%, Limit = 10
4. Click **Start** → watch the agent scan and evaluate jobs
5. Check results in **Dashboard** (live feed) and **Board** (Kanban)
6. Happy with results? Turn Dry Run OFF and run again to actually apply

### From Command Line

```bash
# Dry run — scan 10 jobs, don't apply
python3 -m linkedin_agent run --dry-run --limit 10

# Apply to matching jobs
python3 -m linkedin_agent run --limit 25

# Run as daemon (scheduled, repeating)
python3 -m linkedin_agent daemon

# Check current config
python3 -m linkedin_agent status
```

### Telegram Bot Commands

Start the bot: `python3 -m linkedin_agent.bot`

| Command | What it does |
|---------|-------------|
| `/ping` | Check if your machine is online |
| `/run_agent 10` | Trigger a dry-run scan (10 jobs) |
| `/run_agent 10 --apply` | Scan AND apply |
| `/status` | Agent state + pipeline summary |
| `/logs` | Last run output |
| `/help` | All commands |

---

## 🖥️ Dashboard Pages

| Page | What you do there |
|------|-------------------|
| **Dashboard** | See KPIs, live event feed, score charts, recent activity, top companies |
| **Agent Control** | Start/stop agent, configure threshold + limit (sliders), view live output |
| **Board** | Drag jobs between stages (Discovered → Applied → Interview → Offer) |
| **Scheduler** | Set scan frequency, active hours, urgent mode |
| **Settings** | Configure everything: candidate info, search, Telegram, AI, self-learning |
| **Service** | Background daemon status, start/stop, auto-start toggle |

---

## 🔄 How the Agent Works

```
1. STARTUP       → Launch stealth browser → Check LinkedIn session
                   ↳ Challenge? → Screenshot + Telegram alert → Wait 5 min

2. DISCOVER      → Search keywords × locations → Collect job listings
                   ↳ Urgent mode: 100 jobs/run | Normal: 50/run
                   ↳ First run: past week | After: past 24h

3. EVALUATE      → Already applied? → External? → Score match
                   ↳ Premium AI score OR fallback keyword scoring
                   ↳ Self-learning adjustments (target +15%, blocklist -20%)
                   ↳ Daily cap check (stops at 80/day)

4. APPLY         → Pick right resume → Fill form → Handle questions
                   ↳ Pre-configured answers auto-fill sensitive fields
                   ↳ AI writes cover letters and "why this company"
                   ↳ Unknown fields? → Ask you via Telegram → Fill → Submit
                   ↳ Failed? → Retry queue (3 attempts, backoff)

5. NOTIFY        → Telegram alert per job → InMail draft → Status check
                   ↳ External jobs: sends you the direct link
                   ↳ Response tracking: detects "viewed" / "rejected"
```

---

## 🔒 Safety & Privacy

- **100% self-hosted** — Credentials never leave your machine
- **Human-in-the-loop** — Pauses for unknown fields, asks via Telegram, waits for your answer
- **No telemetry** — Zero analytics, zero outbound calls except LinkedIn + your Telegram bot
- **Dry-run by default** — Test before going live
- **Daily cap** — Stops at 80/day to protect your LinkedIn account
- **Anti-detection** — Stealth browser with rotating fingerprints
- **Open source** — Fully auditable code

---

## 🧠 Self-Learning

The agent gets smarter over time:
- Move a job to "Interviewing" → boosts that company's score
- Reject a job → penalizes that company
- Target companies (Google, Microsoft) get +15% boost from day 1
- Blocklist companies (Wipro, TCS) get -20% penalty from day 1
- All configurable in Settings → Self-Learning

---

## 🏗️ Architecture

Event-driven pipeline designed for multi-platform expansion:

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────┐
│  LinkedIn       │────▶│  Event Bus           │────▶│  Evaluator  │
│  (active)       │     │  • job.discovered    │     │  (scoring)  │
├─────────────────┤     │  • job.qualified     │     └──────┬──────┘
│  Indeed (TBD)   │────▶│  • job.applied       │            │
├─────────────────┤     │  • job.failed        │     ┌──────▼──────┐
│  Naukri (TBD)   │────▶│  • Stage markers     │────▶│  Applicant  │
└─────────────────┘     │  • Dead-letter retry │     └──────┬──────┘
                        └──────────────────────┘            │
                                                     ┌──────▼──────┐
                                                     │  Notifier   │
                                                     └─────────────┘
```

Adding Indeed/Naukri requires only implementing a discovery adapter. Evaluation, application, and notifications are platform-agnostic.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Session expired" | Log into LinkedIn manually in the browser once, session is saved |
| "0 jobs found" | Check if your keywords + locations match real LinkedIn listings |
| Agent stuck / no output | Check `bash service.sh logs` or terminal output |
| "Challenge detected" | Open the screenshot in Telegram, solve CAPTCHA manually, agent resumes |
| Threshold shows wrong % | Dashboard sends integer (70), agent normalizes automatically |
| WebSocket "OFFLINE" | Restart both servers: `bash start.sh` |

---

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

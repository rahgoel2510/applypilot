# ApplyPilot — Complete Guide

> Autonomous LinkedIn Job Application Agent · Powered by Rahul

---

## Table of Contents

- [Architecture](#architecture)
- [Pipeline Flow](#pipeline-flow)
- [Setup (Windows)](#setup-windows)
- [Setup (macOS)](#setup-macos)
- [Configuration](#configuration)
- [Commands](#commands)
- [Telegram Bot](#telegram-bot)
- [Web UI Tabs](#web-ui-tabs)
- [Job Stages](#job-stages)
- [Match Scoring](#match-scoring)
- [InMail Strategy](#inmail-strategy)
- [Scheduler](#scheduler)
- [Auto-Repair (LLM)](#auto-repair-llm)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    YOUR MACHINE                          │
│                                                         │
│  ┌──────────────┐         ┌─────────────────────────┐  │
│  │ LinkedIn     │ ◄──────▶│ Agent (native Python)    │  │
│  │ (Playwright) │         │ - Scans jobs             │  │
│  │              │         │ - Scores via AI coach    │  │
│  │ Uses your    │         │ - Applies (Easy Apply)   │  │
│  │ saved session│         │ - Drafts InMail          │  │
│  └──────────────┘         └──────────┬──────────────┘  │
│                                      │ HTTP             │
│  ┌───────────────────────────────────▼──────────────┐  │
│  │ Tracker (Docker)                                  │  │
│  │ - Web UI (React)       http://localhost:8000      │  │
│  │ - API (FastAPI)                                   │  │
│  │ - SQLite DB (jobs, logs, settings, run history)   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────┐                               │
│  │ Telegram Bot          │ ◄── Notifications, commands  │
│  │ @rg_jobs_bot          │     /run_agent, /status      │
│  └──────────────────────┘                               │
└─────────────────────────────────────────────────────────┘
```

- **Agent** runs natively (needs your LinkedIn browser session)
- **Tracker** runs in Docker (lightweight, no Chromium)
- **Telegram** provides remote control + notifications

---

## Pipeline Flow

```
⚡ Init → 🌐 Browser → 🔐 Session Check
                              │
                    ┌─────────▼──────────┐
                    │  Job Discovery      │
                    │  1. ⭐ Recommended   │
                    │  2. 🔍 Keywords (OR) │
                    │  3. 🔗 Custom URLs   │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │ For each job:       │
                    │  Open page          │
                    │  Click "Show match" │
                    │  Wait for AI score  │
                    │  Parse: 6/8 = 75%   │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
        Score < 80%     Score ≥ 80%      No score
              │          + Easy Apply         │
              ▼               │               ▼
         Stay in           ┌──▼──┐       Stay in
         Discovered        │InMail│       Discovered
                           │Draft │
                           └──┬──┘
                              ▼
                        Reached Out
                              │
                              ▼
                        Easy Apply
                              │
                              ▼
                          Applied
```

---

## Setup (Windows)

### One-time setup:

```powershell
git clone https://github.com/rahgoel2510/applypilot.git
cd applypilot
pip install -r requirements.txt
playwright install chromium
```

### Every time you use it:

```powershell
# 1. Start tracker
docker-compose up -d --build

# 2. Test LinkedIn session
.\test-session.ps1

# 3. Run agent
python -m linkedin_agent run --dry-run --limit 10
```

### To run as scheduled service:
```powershell
python -m linkedin_agent daemon --dry-run
```

---

## Setup (macOS)

```bash
git clone https://github.com/rahgoel2510/applypilot.git
cd applypilot
pip install -r requirements.txt
playwright install chromium

# Start tracker
docker-compose up -d --build

# Test session
python tests/test_browser_dry_run.py --limit 3

# Run agent
python -m linkedin_agent run --dry-run --limit 10
```

---

## Configuration

### `config.yaml`

```yaml
candidate:
  name: "Rahul Goel"
  resume_filename: "RAHUL_GOEL_Resume_Final.pdf"
  notice_period: "30 days"
  willing_to_relocate: true
  work_authorization: "Authorized to work"
  preferred_cities: ["Bangalore", "Hyderabad", "Mumbai", "Delhi NCR"]
  skills:
    - "engineering management"
    - "technical program management"
    - "system design"
    - "agile"
    - "cross-functional leadership"
  resume_mapping:
    - keywords: ["Engineering Manager", "Director of Engineering"]
      resume: "RAHUL_GOEL_EM_Resume.pdf"
    - keywords: ["Technical Program Manager", "TPM"]
      resume: "RAHUL_GOEL_TPM_Resume.pdf"
  sensitive_field_answers:
    salary_expectation: "As per company standards"
    current_ctc: "Confidential - happy to discuss"
    years_of_experience: "12"
  human_input_timeout: 300     # 5 min wait for Telegram reply

job_search:
  keywords:
    - "Engineering Manager"
    - "Technical Program Manager"
    - "Senior Engineering Manager"
    - "Director of Engineering"
  custom_urls:
    - "https://www.linkedin.com/jobs/search-results/?keywords=..."
  locations: ["India", "Bangalore", "Remote"]
  match_threshold: 0.80        # Only apply if ≥ 80% match
  max_postings_per_run: 50
  posted_within: "24h"         # 24h, week, month, any
  initial_scan_window: "week"  # First-ever run scans past week
  skip_external_apply: false   # Track external jobs (notify via Telegram)
  track_external_apply: true
  fallback_scoring: true       # Keyword scoring when no Premium
  daily_application_limit: 80  # Stop at 80/day to avoid rate limits

scheduler:
  interval_minutes: 60         # Run every hour
  active_hours_start: 9        # Start at 9 AM
  active_hours_end: 22         # Stop at 10 PM
  urgent_mode: true            # First-week sprint mode
  urgent_interval_minutes: 30  # Every 30 min in urgent
  urgent_max_postings: 100     # More jobs per run
  urgent_duration_days: 7      # Auto-disable after 7 days

telegram:
  notify_on_submit: true
  notify_on_pause: true

inmail:
  enabled: true
  tone: "professional"
  max_length: 300

self_learning:
  target_companies: ["Google", "Microsoft", "Amazon"]
  blocklist_companies: ["Wipro", "Infosys", "TCS"]
  target_boost: 0.15           # +15% score boost for targets
  blocklist_penalty: 0.20      # -20% score penalty for blocklist
```

### `.env`

```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
OPENAI_API_KEY=sk-or-v1-your-openrouter-key
AI_MODEL=openrouter/free
LINKEDIN_EMAIL=your@email.com
LINKEDIN_PASSWORD=your_password
```

---

## Commands

| Command | What it does |
|---------|-------------|
| `python -m linkedin_agent run --dry-run --limit 10` | Scan 10 jobs, don't apply |
| `python -m linkedin_agent run --limit 25` | Scan 25 jobs, apply to matches |
| `python -m linkedin_agent daemon --dry-run` | Scheduled scans (every 60min) |
| `python -m linkedin_agent daemon` | Scheduled + auto-apply |
| `python -m linkedin_agent status` | Show config summary |
| `python -m linkedin_agent.bot` | Start Telegram command bot |
| `.\test-session.ps1` | Test LinkedIn session (Windows) |

---

## Telegram Bot

Start: `python -m linkedin_agent.bot`

| Command | Description |
|---------|-------------|
| `/ping` | Check if machine is online |
| `/run_agent 10` | Trigger dry-run scan (10 jobs) |
| `/run_agent 10 --apply` | Scan AND apply |
| `/status` | Agent state + board summary |
| `/track_status` | Full Kanban board |
| `/logs` | Last run (GitHub Actions style) |
| `/schedule` | Scheduler config |
| `/help` | All commands |

---

## Web UI Tabs

Access: **http://localhost:8000**

| Tab | Purpose |
|-----|---------|
| **Dashboard** | Stats + live activity feed |
| **Agent** | Pipeline viz + control panel + run history |
| **Board** | Kanban drag-and-drop (7 columns) |
| **Activity Log** | Full event timeline with filters |
| **Tech Logs** | Raw agent output (copiable) |
| **Settings** | API keys, model selection, test connections |

---

## Job Stages

```
Discovered → Reached Out → Saved → Applied → Interviewing → Offered → Rejected
```

| Stage | Meaning |
|-------|---------|
| **Discovered** | Found by agent, score checked, added to tracker |
| **Reached Out** | InMail drafted and sent to recruiter (warm inbound) |
| **Saved** | Paused — needs human input (CTC, visa, etc.) |
| **Applied** | Easy Apply submitted successfully |
| **Interviewing** | Interview scheduled (drag manually) |
| **Offered** | Offer received (drag manually) |
| **Rejected** | Application rejected (drag manually) |

---

## Match Scoring

### Primary: LinkedIn Premium AI Coach

1. Agent opens job page
2. Clicks "Show match details"
3. LinkedIn AI evaluates your profile vs. job requirements
4. Returns: "Matches 6 of 8 required qualifications"
5. Agent computes: 6/8 = 75%
6. If ≥ 80% → apply. If < 80% → skip.

### Fallback: Keyword Scoring (No Premium Required)

When LinkedIn AI doesn't return a score:
1. Agent uses `FallbackScorer` — TF-IDF-like keyword overlap
2. Matches job title + company against your configured skills + keywords
3. Gives bonus for exact title matches and location matches
4. Returns a 0.0–1.0 score, same threshold applies

### Self-Learning Score Adjustments

- Target companies (configured): +15% boost
- Blocklist companies (configured): -20% penalty
- Promoted to interview (learned): +10% boost
- Rejected by you (learned): -10% penalty

---

## InMail Strategy

### Post-Submission Only (Easy Apply)

```
Score ≥ 80% → Apply → Success? → Draft InMail → Send to Telegram for review
```

InMail is only drafted AFTER confirmed submission. Never message a recruiter about a job you didn't apply to.

### External Apply (High Match)

```
Score ≥ 80% + External → Draft InMail → Notify user via Telegram with direct link
```

For external jobs, InMail serves as a warm intro since user applies manually.

### InMail Prompt

The AI drafts with these rules:
- No AI buzzwords (no "spearheaded", "leverage", "passionate")
- Short: under 150 words
- Specific: references the job title and company
- Human: sounds like a real professional, not a template
- Structure: Hook → Value prop (with numbers) → Soft CTA

---

## Scheduler

```yaml
scheduler:
  interval_minutes: 60
  active_hours_start: 9
  active_hours_end: 22
```

Run: `python -m linkedin_agent daemon --dry-run`

Behavior:
- Scans every 60 minutes
- Only runs between 9:00 AM and 10:00 PM
- Sends Telegram: "⏰ Scheduled scan starting"
- After each cycle: "📊 Applied: 3 | Skipped: 5 | Next: ~60min"
- Sleeps silently outside active hours
- Press Ctrl+C to stop gracefully

---

## Auto-Repair (LLM)

When a run fails, the agent can self-diagnose:

1. Sends error + context to OpenRouter
2. LLM returns structured diagnosis:
   - Category: session / selector / timeout / config
   - Severity: low / medium / high / critical
   - Fix: what to do
   - Auto-fixable: yes/no
3. If auto-fixable → retries with adjusted parameters

Access from UI: Run History → expand failed run → "AI Diagnose" / "Auto-Repair & Retry"

---

## Troubleshooting

### "Session expired" / "Not logged in"

```powershell
.\test-session.ps1
# If expired → opens browser → log in → saved
```

### "Found 0 jobs"

1. Check session is valid (run test above)
2. Check `config.yaml` keywords are correct
3. Try `posted_within: "week"` (broader than "24h")

### "No score (LinkedIn Premium needed)"

- The "Show match details" AI takes 5-15 seconds per job
- Requires LinkedIn Premium subscription
- If not Premium: agent keeps jobs in Discovered for manual review

### Telegram errors with `<input` tags

Fixed — error messages are sanitized before sending to Telegram.

### Docker "0/6 configured"

```powershell
docker-compose down
docker-compose up -d --build
# env_file: .env passes your secrets to Docker
```

### Agent crashes on custom URL

Fixed — `card.as_element()` null check added. Pull latest and retry.

---

## Project Links

- **GitHub**: https://github.com/rahgoel2510/applypilot
- **Landing Page**: https://rahgoel2510.github.io/applypilot/
- **Ko-fi**: https://ko-fi.com/goelrah

---

*Powered by Rahul*

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
  <a href="#features">Features</a> •
  <a href="#screenshots">Screenshots</a> •
  <a href="https://ko-fi.com/goelrah">Ko-fi</a>
</p>

---

**ApplyPilot** is a fully autonomous agent that scans LinkedIn for jobs matching your profile, scores them for relevance, and applies on your behalf using Easy Apply — all while keeping you in the loop for sensitive decisions. It runs as a self-hosted daemon with a beautiful Kanban tracker UI, so you never lose sight of your pipeline.

## 🚀 Features

- 🔍 **Auto-Scan** — Continuously monitors LinkedIn for new job postings matching your saved searches and keywords.
- 📊 **Match Scoring** — AI-powered relevance scoring ranks jobs by fit against your resume, skills, and preferences.
- ⚡ **Easy Apply Automation** — Fills and submits LinkedIn Easy Apply forms end-to-end, handling multi-step flows.
- 🧑‍💼 **Human-in-the-Loop** — Pauses and asks you before answering sensitive fields (CTC, notice period, visa status).
- 📬 **Telegram Notifications** — Real-time alerts for new matches, successful applications, and fields needing your input.
- ✉️ **InMail Drafting** — Generates personalized cold outreach messages to hiring managers and recruiters.
- 📋 **Kanban Tracker** — Built-in web dashboard with drag-and-drop board, activity logs, and per-application timeline.
- 🧪 **Dry-Run Mode** — Preview what the agent would do without actually submitting any applications.
- 🖥️ **Cross-Platform Daemon** — Runs as a background service on macOS, Linux, and Windows (via Docker or native).
- 🐳 **Docker One-Line Deploy** — Get up and running in seconds with a single `curl` command.

## 📦 Quick Start

### One-liner install

```bash
curl -fsSL https://raw.githubusercontent.com/rahgoel2510/applypilot/main/install.sh | bash
```

### Or with docker-compose

```yaml
# docker-compose.yml
version: "3.8"
services:
  applypilot:
    image: rahgoel2510/applypilot:latest
    container_name: applypilot
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./data:/app/data
    environment:
      - TZ=Asia/Kolkata
```

```bash
docker-compose up -d
```

Open **http://localhost:8000** to access the tracker dashboard.

## 🖥️ Tracker Dashboard

ApplyPilot ships with a built-in web UI at `http://localhost:8000` featuring four tabs:

| Tab | Description |
|-----|-------------|
| **Dashboard** | At-a-glance stats — applications sent today, match rate, pending reviews, weekly trends. |
| **Agent Control** | Start/stop the agent, toggle dry-run mode, adjust scan frequency, and view live logs. |
| **Board** | Kanban-style board with columns: Matched → Applied → Interview → Offer → Rejected. Drag cards between stages. |
| **Activity Log** | Chronological feed of every action the agent took, with timestamps and expandable details. |

## ⚙️ Configuration

Create a `config.yaml` in your project directory:

```yaml
linkedin:
  email: your-email@example.com
  password: ${LINKEDIN_PASSWORD}    # or use env var
  session_cookie: ""                # optional: paste li_at cookie

search:
  keywords: ["Software Engineer", "Backend Developer"]
  locations: ["Bengaluru", "Remote"]
  experience_level: ["Mid-Senior", "Senior"]
  posted_within: "24h"

scoring:
  min_match_score: 70               # 0-100, skip jobs below this
  resume_path: ./resume.pdf

apply:
  dry_run: false
  max_applications_per_day: 25
  human_in_loop_fields:
    - current_ctc
    - expected_ctc
    - notice_period

notifications:
  telegram:
    enabled: true
    bot_token: ${TELEGRAM_BOT_TOKEN}
    chat_id: ${TELEGRAM_CHAT_ID}

server:
  port: 8000
  host: 0.0.0.0
```

## 🔒 Safety & Privacy

- **100% Self-Hosted** — Your credentials and data never leave your machine. No third-party servers involved.
- **Human-in-the-Loop** — The agent will never guess your CTC, notice period, or other sensitive fields. It pauses and asks you via Telegram or the web UI.
- **No Data Exfiltration** — Zero telemetry, zero analytics, zero outbound calls except to LinkedIn and your configured Telegram bot.
- **Dry-Run by Default** — First run starts in dry-run mode so you can verify behavior before going live.
- **Open Source** — Fully auditable. Read every line of code that touches your LinkedIn account.

## 🛠️ Development

```bash
# Clone the repo
git clone https://github.com/rahgoel2510/applypilot.git
cd applypilot

# Install dependencies
pip install -r requirements.txt

# Copy and edit config
cp config.example.yaml config.yaml

# Run the agent locally
python -m applypilot serve

# Run tests
pytest tests/ -v
```

**Requirements:** Python 3.11+, Chrome/Chromium (for browser automation), Docker (optional).

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

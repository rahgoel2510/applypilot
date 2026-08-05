#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════
# ApplyPilot — One-Script Setup
# Run this on a fresh macOS/Linux laptop to install everything needed.
# Usage: bash setup.sh
# ═══════════════════════════════════════════════════════════════════════

BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

log()   { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }
header(){ echo -e "\n${BOLD}═══ $1 ═══${NC}\n"; }

header "ApplyPilot Setup"
echo "This script will install all prerequisites and set up the app."
echo ""

# ─── Detect OS ───────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"
log "Detected: $OS ($ARCH)"

# ─── 1. Homebrew (macOS) or apt (Linux) ─────────────────────────────
header "1. Package Manager"

if [[ "$OS" == "Darwin" ]]; then
  if ! command -v brew &>/dev/null; then
    log "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
    ok "Homebrew installed"
  else
    ok "Homebrew already installed"
  fi
elif [[ "$OS" == "Linux" ]]; then
  if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    ok "apt updated"
  fi
fi

# ─── 2. Python 3.11+ ────────────────────────────────────────────────
header "2. Python"

install_python() {
  if [[ "$OS" == "Darwin" ]]; then
    brew install python@3.12
  else
    sudo apt-get install -y python3 python3-pip python3-venv
  fi
}

if command -v python3 &>/dev/null; then
  PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
  PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
  if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 11 ]]; then
    ok "Python $PY_VER ✓"
  else
    warn "Python $PY_VER found but 3.11+ required. Installing..."
    install_python
  fi
else
  log "Installing Python 3.12..."
  install_python
fi

# ─── 3. Node.js 18+ ─────────────────────────────────────────────────
header "3. Node.js"

if command -v node &>/dev/null; then
  NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
  if [[ "$NODE_VER" -ge 18 ]]; then
    ok "Node.js $(node -v) ✓"
  else
    warn "Node.js v$NODE_VER found but 18+ required. Installing..."
    if [[ "$OS" == "Darwin" ]]; then brew install node; else curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs; fi
  fi
else
  log "Installing Node.js..."
  if [[ "$OS" == "Darwin" ]]; then brew install node; else curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs; fi
fi
ok "Node.js $(node -v), npm $(npm -v)"

# ─── 4. Chrome/Chromium (for Playwright) ────────────────────────────
header "4. Browser (Chromium)"

if [[ "$OS" == "Darwin" ]]; then
  if [[ -d "/Applications/Google Chrome.app" ]] || [[ -d "/Applications/Chromium.app" ]]; then
    ok "Chrome/Chromium found"
  else
    log "Installing Chromium..."
    brew install --cask chromium
  fi
else
  if command -v chromium-browser &>/dev/null || command -v google-chrome &>/dev/null; then
    ok "Chrome/Chromium found"
  else
    sudo apt-get install -y chromium-browser
  fi
fi

# ─── 5. Project Setup ────────────────────────────────────────────────
header "5. Project Dependencies"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
log "Working in: $PROJECT_DIR"

# Python virtual environment
if [[ ! -d ".venv" ]]; then
  log "Creating Python virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate
ok "Virtual env activated"

# Python dependencies
log "Installing Python packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -r tracker/backend/requirements.txt -q

# Optional: Turso cloud dedup
log "Trying optional libsql-experimental (cloud dedup)..."
if pip install libsql-experimental -q 2>/dev/null; then
  ok "libsql-experimental installed (Turso cloud dedup enabled)"
else
  warn "libsql-experimental skipped (dedup will use local SQLite)"
fi
ok "Python packages installed"

# Playwright browsers
log "Installing Playwright browsers..."
python -m playwright install chromium 2>/dev/null || pip install playwright -q && python -m playwright install chromium
ok "Playwright Chromium installed"

# Frontend dependencies
log "Installing frontend packages..."
cd tracker/frontend
npm install --silent
cd "$PROJECT_DIR"
ok "Frontend packages installed"

# ─── 6. Environment Configuration ───────────────────────────────────
header "6. Environment"

if [[ ! -f ".env" ]]; then
  log "Creating .env from template..."
  cp .env.example .env
  warn "Edit .env with your Telegram bot token and LinkedIn credentials"
else
  ok ".env exists"
fi

if [[ ! -f "config.yaml" ]]; then
  log "Creating config.yaml from template..."
  cp config.yaml.example config.yaml
  warn "Edit config.yaml with your candidate info, keywords, and locations"
else
  ok "config.yaml exists"
fi

# ─── 7. Database Setup (Isolated per environment) ────────────────────
header "7. Database"

# Each environment gets its own isolated SQLite databases
# Tracker DB (local)
cd tracker/backend
python3 -c "
from database import Base, engine
from models import Job, ActivityLog, AppSetting, AgentRun, FeedbackSignal, InMailDraft
Base.metadata.create_all(bind=engine)
print('Tracker DB initialized')
" 2>/dev/null || log "Tracker DB will be created on first run"
cd "$PROJECT_DIR"

# Dedup DB — uses Turso cloud (isolated per environment)
# Each environment should use its own Turso database URL
log "Dedup DB: configure TURSO_URL and TURSO_TOKEN in .env for cloud isolation"
log "  Create a new Turso DB: turso db create applypilot-\$(hostname -s)"
log "  Get token: turso db tokens create applypilot-\$(hostname -s)"

ok "Database setup complete"

# ─── 8. Build Frontend ───────────────────────────────────────────────
header "8. Build"

cd tracker/frontend
log "Building frontend..."
npx vite build --quiet 2>/dev/null || npx vite build
cd "$PROJECT_DIR"

# Copy built assets for production serving
if [[ -d "tracker/frontend/dist" ]]; then
  rm -rf tracker/backend/static
  cp -r tracker/frontend/dist tracker/backend/static
  ok "Frontend built and deployed to backend/static"
fi

# ─── 9. Verify ───────────────────────────────────────────────────────
header "9. Verification"

python3 -c "import linkedin_agent; print('Agent module: OK')" 2>/dev/null && ok "Agent module" || warn "Agent module import issue (non-critical)"
python3 -c "from tracker.backend.main import app; print('Backend: OK')" 2>/dev/null && ok "Backend" || warn "Backend import issue"
node -e "console.log('Node: OK')" && ok "Node.js runtime"

# ─── Done! ───────────────────────────────────────────────────────────
header "✅ Setup Complete!"

cat << 'EOF'

To start ApplyPilot:

  1. Start the tracker (dashboard + API):
     cd tracker/backend && uvicorn main:app --port 8000

  2. Start the frontend (dev mode):
     cd tracker/frontend && npm run dev

  3. Run the agent:
     python -m linkedin_agent serve --dry-run

  Or run everything in one command:
     bash start.sh

Dashboard: http://localhost:5173 (dev) or http://localhost:8000 (production)

───────────────────────────────────────────────
Environment Isolation:
  • Tracker DB: ./tracker/backend/tracker.db (local per machine)
  • Dedup DB: Turso cloud (set TURSO_URL per env in .env)
  • Config: ./config.yaml (per machine)
  • Secrets: .env file (never committed)
───────────────────────────────────────────────

EOF

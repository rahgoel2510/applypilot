#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# ApplyPilot — Start All Services
# ═══════════════════════════════════════════════════════════════

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Activate venv if exists
if [[ -f ".venv/bin/activate" ]]; then
  source .venv/bin/activate
fi

# Load .env
if [[ -f ".env" ]]; then
  set -a; source .env; set +a
fi

# ─── First-Run Detection ─────────────────────────────────────
FIRST_RUN=false

if [[ ! -f ".env" ]]; then
  echo "⚠️  No .env file found!"
  echo ""
  echo "   Run setup first:  bash setup.sh"
  echo "   Or copy manually: cp .env.example .env"
  echo ""
  exit 1
fi

if [[ ! -f "config.yaml" ]]; then
  if [[ -f "config.yaml.example" ]]; then
    echo "📋 First run detected — creating config.yaml from template..."
    cp config.yaml.example config.yaml
    FIRST_RUN=true
  fi
fi

# Generate API key if not set
if [[ -z "${APPLYPILOT_API_KEY:-}" ]]; then
  GENERATED_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || echo "")
  if [[ -n "$GENERATED_KEY" ]]; then
    echo "APPLYPILOT_API_KEY=$GENERATED_KEY" >> .env
    export APPLYPILOT_API_KEY="$GENERATED_KEY"
    echo "🔑 Generated API key (saved to .env)"
  fi
fi

echo "🚀 Starting ApplyPilot..."
echo ""

# Kill any existing processes
pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "vite --port 5173" 2>/dev/null || true
sleep 1

# Start backend
echo "📡 Starting backend (port 8000)..."
cd tracker/backend
nohup uvicorn main:app --reload --port 8000 > /tmp/applypilot-backend.log 2>&1 &
BACKEND_PID=$!
cd "$PROJECT_DIR"

# Start frontend
echo "🎨 Starting frontend (port 5173)..."
cd tracker/frontend
nohup npx vite --port 5173 > /tmp/applypilot-frontend.log 2>&1 &
FRONTEND_PID=$!
cd "$PROJECT_DIR"

sleep 3

echo ""
echo "✅ ApplyPilot is running!"
echo ""
echo "   Dashboard:  http://localhost:5173"
echo "   API:        http://localhost:8000"
echo ""
echo "   Backend PID:  $BACKEND_PID"
echo "   Frontend PID: $FRONTEND_PID"
echo ""

if [[ "$FIRST_RUN" == "true" ]]; then
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  🎉 FIRST RUN — Welcome to ApplyPilot!                     ║"
  echo "║                                                            ║"
  echo "║  Open http://localhost:5173 and go to Settings to:         ║"
  echo "║    1. Enter your name, skills, and resume                  ║"
  echo "║    2. Set your target job keywords and locations           ║"
  echo "║    3. Configure Telegram notifications                     ║"
  echo "║                                                            ║"
  echo "║  Then go to Agent Control → Start (Dry Run ON) to test.   ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
  echo ""
fi

echo "   Logs: tail -f /tmp/applypilot-backend.log"
echo "         tail -f /tmp/applypilot-frontend.log"
echo ""
echo "   To stop: pkill -f uvicorn; pkill -f vite"
echo ""

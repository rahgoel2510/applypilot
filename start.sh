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
echo "   Logs: tail -f /tmp/applypilot-backend.log"
echo "         tail -f /tmp/applypilot-frontend.log"
echo ""
echo "   To stop: pkill -f uvicorn; pkill -f vite"
echo ""

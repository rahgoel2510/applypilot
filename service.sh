#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# ApplyPilot — Run as Background Service (macOS/Linux)
# ═══════════════════════════════════════════════════════════════
# Installs as a persistent background service using launchd (macOS)
# or systemd (Linux). Survives reboots.
#
# Usage:
#   bash service.sh install    # Install & start as background service
#   bash service.sh start      # Start the service
#   bash service.sh stop       # Stop the service
#   bash service.sh status     # Check if running
#   bash service.sh logs       # View logs
#   bash service.sh uninstall  # Remove the service
# ═══════════════════════════════════════════════════════════════

BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()   { echo -e "${GREEN}[OK]${NC}    $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="com.applypilot.tracker"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$PROJECT_DIR/.service.pid"

mkdir -p "$LOG_DIR"

# ─── macOS (launchd) ────────────────────────────────────────

install_macos() {
    local plist="$HOME/Library/LaunchAgents/$SERVICE_NAME.plist"

    cat > "$plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$SERVICE_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/.venv/bin/uvicorn</string>
        <string>main:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR/tracker/backend</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>PYTHONPATH</key>
        <string>$PROJECT_DIR</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/backend.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/backend-error.log</string>
</dict>
</plist>
EOF

    launchctl load "$plist" 2>/dev/null
    launchctl start "$SERVICE_NAME" 2>/dev/null
    ok "Installed macOS service: $SERVICE_NAME"
    ok "Backend runs on http://localhost:8000"
    log "Logs: $LOG_DIR/backend.log"
    log "To stop: bash service.sh stop"
    log "Auto-starts on login ✓"
}

uninstall_macos() {
    local plist="$HOME/Library/LaunchAgents/$SERVICE_NAME.plist"
    launchctl stop "$SERVICE_NAME" 2>/dev/null || true
    launchctl unload "$plist" 2>/dev/null || true
    rm -f "$plist"
    ok "Service uninstalled"
}

start_macos() {
    launchctl start "$SERVICE_NAME" 2>/dev/null
    ok "Service started"
}

stop_macos() {
    launchctl stop "$SERVICE_NAME" 2>/dev/null
    ok "Service stopped"
}

status_macos() {
    if launchctl list | grep -q "$SERVICE_NAME"; then
        ok "Service is RUNNING"
        echo "  URL: http://localhost:8000"
    else
        warn "Service is STOPPED"
    fi
}

# ─── Linux (systemd) ────────────────────────────────────────

install_linux() {
    local unit="$HOME/.config/systemd/user/$SERVICE_NAME.service"
    mkdir -p "$(dirname "$unit")"

    cat > "$unit" << EOF
[Unit]
Description=ApplyPilot Tracker
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR/tracker/backend
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin"
Environment="PYTHONPATH=$PROJECT_DIR"
ExecStart=$PROJECT_DIR/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:$LOG_DIR/backend.log
StandardError=append:$LOG_DIR/backend-error.log

[Install]
WantedBy=default.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable "$SERVICE_NAME"
    systemctl --user start "$SERVICE_NAME"
    ok "Installed systemd user service: $SERVICE_NAME"
    ok "Backend runs on http://localhost:8000"
    log "Logs: journalctl --user -u $SERVICE_NAME -f"
    log "Auto-starts on login ✓"
}

uninstall_linux() {
    systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/$SERVICE_NAME.service"
    systemctl --user daemon-reload
    ok "Service uninstalled"
}

start_linux() { systemctl --user start "$SERVICE_NAME"; ok "Started"; }
stop_linux() { systemctl --user stop "$SERVICE_NAME"; ok "Stopped"; }
status_linux() {
    if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        ok "Service is RUNNING"
        echo "  URL: http://localhost:8000"
    else
        warn "Service is STOPPED"
    fi
}

# ─── Command dispatch ────────────────────────────────────────

OS="$(uname -s)"
CMD="${1:-status}"

case "$CMD" in
    install)
        log "Installing ApplyPilot as background service..."
        if [[ "$OS" == "Darwin" ]]; then install_macos; else install_linux; fi
        ;;
    uninstall)
        if [[ "$OS" == "Darwin" ]]; then uninstall_macos; else uninstall_linux; fi
        ;;
    start)
        if [[ "$OS" == "Darwin" ]]; then start_macos; else start_linux; fi
        ;;
    stop)
        if [[ "$OS" == "Darwin" ]]; then stop_macos; else stop_linux; fi
        ;;
    status)
        if [[ "$OS" == "Darwin" ]]; then status_macos; else status_linux; fi
        ;;
    logs)
        tail -f "$LOG_DIR/backend.log"
        ;;
    *)
        echo "Usage: bash service.sh {install|start|stop|status|logs|uninstall}"
        exit 1
        ;;
esac

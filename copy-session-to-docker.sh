#!/bin/bash
# ─── Copy your LinkedIn browser session into the Docker container ───
#
# Works on Mac, Linux, and Windows (Git Bash / WSL).
#
# Steps:
#   1. Log in locally first:  python tests/test_browser_dry_run.py --limit 3
#   2. Run this:              ./copy-session-to-docker.sh
#
set -e

CONTAINER="applypilot"
# This is the path INSIDE the container (always Linux, always the same)
CONTAINER_PATH="/root/.local/share/linkedin_agent/browser_data"

echo "📋 Copying LinkedIn browser session into Docker..."
echo ""

# Detect OS and find local session
if [[ "$OSTYPE" == "darwin"* ]]; then
    SESSION_DIR="$HOME/Library/Application Support/linkedin_agent/browser_data"
elif [[ -n "$LOCALAPPDATA" ]]; then
    # Windows (Git Bash / MSYS)
    SESSION_DIR="$LOCALAPPDATA/linkedin_agent/browser_data"
else
    SESSION_DIR="$HOME/.local/share/linkedin_agent/browser_data"
fi

echo "   Host OS session: $SESSION_DIR"
echo "   Container path:  $CONTAINER_PATH"
echo ""

if [ ! -d "$SESSION_DIR" ]; then
    echo "❌ No local session found."
    echo ""
    echo "   Run this first to log in and create a session:"
    echo "   python tests/test_browser_dry_run.py --limit 3"
    exit 1
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "❌ Container '${CONTAINER}' is not running."
    echo "   Start it with: docker-compose up -d"
    exit 1
fi

# Create target directory and copy
docker exec "$CONTAINER" mkdir -p "$CONTAINER_PATH"
docker cp "$SESSION_DIR/." "$CONTAINER:$CONTAINER_PATH/"

echo "✅ Done! Session copied into Docker."
echo ""
echo "   Open http://localhost:8000/#agent → Launch Agent"

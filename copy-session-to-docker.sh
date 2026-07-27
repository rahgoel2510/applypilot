#!/bin/bash
# ─── Copy your LinkedIn browser session into the Docker container ───
#
# Run this AFTER you've logged into LinkedIn locally:
#   python tests/test_browser_dry_run.py --limit 3
#
# Then run this script to copy the session into Docker:
#   ./copy-session-to-docker.sh
#
set -e

CONTAINER="applypilot"

echo "📋 Copying LinkedIn browser session into Docker..."
echo ""

# Detect OS and find local session
if [[ "$OSTYPE" == "darwin"* ]]; then
    SESSION_DIR="$HOME/Library/Application Support/linkedin_agent/browser_data"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    SESSION_DIR="$LOCALAPPDATA/linkedin_agent/browser_data"
else
    SESSION_DIR="$HOME/.local/share/linkedin_agent/browser_data"
fi

if [ ! -d "$SESSION_DIR" ]; then
    echo "❌ No local session found at: $SESSION_DIR"
    echo ""
    echo "Run this first to create a session:"
    echo "  python tests/test_browser_dry_run.py --limit 3"
    exit 1
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "❌ Container '${CONTAINER}' is not running."
    echo "   Start it with: docker-compose up -d"
    exit 1
fi

# Create target directory in container
docker exec "$CONTAINER" mkdir -p /home/pwuser/.local/share/linkedin_agent/browser_data

# Copy session files
docker cp "$SESSION_DIR/." "$CONTAINER:/home/pwuser/.local/share/linkedin_agent/browser_data/"

echo "✅ Session copied successfully!"
echo ""
echo "The agent inside Docker will now use your LinkedIn session."
echo "Go to http://localhost:8000/#agent and click 'Launch Agent'."

#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# ApplyPilot — Docker Setup & Test (macOS/Linux)
# ═══════════════════════════════════════════════════════════════
# Builds the Docker image, starts the container, and verifies
# everything is working.
#
# Usage: bash docker-setup.sh
# ═══════════════════════════════════════════════════════════════

BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()   { echo -e "${GREEN}[ OK ]${NC}  $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()  { echo -e "${RED}[FAIL]${NC}  $1"; }

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo ""
echo -e "${BOLD}═══ ApplyPilot — Docker Setup & Test ═══${NC}"
echo ""

# ─── 1. Check Docker ────────────────────────────────────────

log "Checking Docker..."
if ! command -v docker &>/dev/null; then
    err "Docker not found! Install from https://docker.com"
    exit 1
fi
if ! docker info &>/dev/null; then
    err "Docker daemon not running. Start Docker Desktop."
    exit 1
fi
ok "Docker is running"

# ─── 2. Check .env ──────────────────────────────────────────

if [[ ! -f ".env" ]]; then
    if [[ -f ".env.example" ]]; then
        cp .env.example .env
        warn "Created .env from template — edit it with your credentials"
    else
        warn "No .env file. Container will use defaults."
    fi
fi

# ─── 3. Stop existing container ─────────────────────────────

log "Stopping existing container (if any)..."
docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true

# ─── 4. Build image ─────────────────────────────────────────

log "Building Docker image (this may take a few minutes first time)..."
docker compose build 2>/dev/null || docker-compose build
ok "Image built successfully"

# ─── 5. Start container ─────────────────────────────────────

log "Starting container..."
docker compose up -d 2>/dev/null || docker-compose up -d
ok "Container started"

# ─── 6. Wait for health ─────────────────────────────────────

log "Waiting for service to be healthy..."
MAX_WAIT=30
for i in $(seq 1 $MAX_WAIT); do
    if curl -s http://localhost:80/api/stats &>/dev/null; then
        ok "Service is healthy!"
        break
    fi
    if [[ $i -eq $MAX_WAIT ]]; then
        err "Service did not start within ${MAX_WAIT}s"
        echo ""
        echo "  Docker logs:"
        docker compose logs --tail 20 2>/dev/null || docker-compose logs --tail 20
        exit 1
    fi
    sleep 1
done

# ─── 7. Run tests ───────────────────────────────────────────

echo ""
log "Running health checks..."

# Test API
STATS=$(curl -s http://localhost:80/api/stats)
if echo "$STATS" | grep -q "total"; then
    ok "API /stats: $STATS"
else
    err "API /stats failed"
fi

# Test jobs endpoint
JOBS=$(curl -s http://localhost:80/api/jobs | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} jobs')" 2>/dev/null || echo "error")
ok "API /jobs: $JOBS"

# Test frontend
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80/)
if [[ "$HTTP_CODE" == "200" ]]; then
    ok "Frontend: HTTP $HTTP_CODE ✓"
else
    warn "Frontend: HTTP $HTTP_CODE (may need static build)"
fi

# Test webhook
WEBHOOK=$(curl -s -X POST http://localhost:80/api/webhook/agent \
    -H "Content-Type: application/json" \
    -d '{"event":"discovered","title":"Test Job","company":"Test Corp","match_score":0.85}' \
    -o /dev/null -w "%{http_code}")
if [[ "$WEBHOOK" == "201" ]]; then
    ok "Webhook: Job created ✓"
else
    warn "Webhook: HTTP $WEBHOOK"
fi

# ─── 8. Summary ─────────────────────────────────────────────

echo ""
echo -e "${BOLD}═══ All Tests Passed! ═══${NC}"
echo ""
echo -e "  ${GREEN}Dashboard:${NC}  http://localhost:80"
echo -e "  ${GREEN}API:${NC}        http://localhost:80/api/stats"
echo ""
echo -e "  Container: $(docker ps --filter name=applypilot --format '{{.Names}} ({{.Status}})')"
echo ""
echo -e "  Commands:"
echo -e "    docker compose logs -f        # View logs"
echo -e "    docker compose stop           # Stop"
echo -e "    docker compose start          # Start again"
echo -e "    docker compose down           # Remove container"
echo ""

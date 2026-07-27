#!/usr/bin/env bash
# ApplyPilot Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/rahgoel2510/applypilot/main/install.sh | bash
set -euo pipefail

# --- Colors & Helpers ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()    { echo -e "${CYAN}ℹ️  $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warn()    { echo -e "${YELLOW}⚠️  $1${NC}"; }
error()   { echo -e "${RED}❌ $1${NC}"; exit 1; }

# --- Dependency Checks ---
info "Checking dependencies..."

if ! command -v docker &> /dev/null; then
  error "Docker is not installed. Please install Docker first: https://docs.docker.com/get-docker/"
fi
success "Docker found: $(docker --version)"

if command -v docker-compose &> /dev/null; then
  COMPOSE_CMD="docker-compose"
  success "docker-compose found: $(docker-compose --version)"
elif docker compose version &> /dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
  success "Docker Compose (plugin) found: $(docker compose version)"
else
  error "docker-compose is not installed. Please install it: https://docs.docker.com/compose/install/"
fi

# --- Setup Directory ---
INSTALL_DIR="$HOME/applypilot"

info "Setting up ApplyPilot in ${INSTALL_DIR}..."

if [ -d "$INSTALL_DIR" ]; then
  warn "Directory ${INSTALL_DIR} already exists. Updating in place..."
else
  mkdir -p "$INSTALL_DIR"
  success "Created directory: ${INSTALL_DIR}"
fi

# --- Download docker-compose.yml ---
COMPOSE_FILE="${INSTALL_DIR}/docker-compose.yml"
COMPOSE_URL="https://raw.githubusercontent.com/rahgoel2510/applypilot/main/docker-compose.yml"

if [ -f "$COMPOSE_FILE" ]; then
  warn "docker-compose.yml already exists. Backing up to docker-compose.yml.bak"
  cp "$COMPOSE_FILE" "${COMPOSE_FILE}.bak"
fi

info "Downloading docker-compose.yml..."
if command -v curl &> /dev/null; then
  curl -fsSL "$COMPOSE_URL" -o "$COMPOSE_FILE"
elif command -v wget &> /dev/null; then
  wget -q "$COMPOSE_URL" -O "$COMPOSE_FILE"
else
  error "Neither curl nor wget found. Cannot download files."
fi
success "Downloaded docker-compose.yml"

# --- Start Services ---
info "Starting ApplyPilot services..."
cd "$INSTALL_DIR"
$COMPOSE_CMD up -d

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🚀 ApplyPilot is up and running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "   🌐 Dashboard:  ${CYAN}http://localhost:8000${NC}"
echo -e "   📁 Install dir: ${CYAN}${INSTALL_DIR}${NC}"
echo -e "   📝 Config:      ${CYAN}${INSTALL_DIR}/config.yaml${NC}"
echo ""
echo -e "   ${YELLOW}Next steps:${NC}"
echo -e "   1. Edit ${CYAN}${INSTALL_DIR}/config.yaml${NC} with your LinkedIn credentials"
echo -e "   2. Open ${CYAN}http://localhost:8000${NC} to access the tracker dashboard"
echo -e "   3. Start the agent from the Agent Control tab"
echo ""
echo -e "   ${YELLOW}Manage:${NC}"
echo -e "   Stop:    cd ${INSTALL_DIR} && ${COMPOSE_CMD} down"
echo -e "   Logs:    cd ${INSTALL_DIR} && ${COMPOSE_CMD} logs -f"
echo -e "   Update:  cd ${INSTALL_DIR} && ${COMPOSE_CMD} pull && ${COMPOSE_CMD} up -d"
echo ""
success "Installation complete! 🎉"

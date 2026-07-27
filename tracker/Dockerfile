# ─── Stage 1: Build React Frontend ────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY tracker/frontend/package.json tracker/frontend/package-lock.json ./
RUN npm ci
COPY tracker/frontend/ ./
RUN npm run build


# ─── Stage 2: Full ApplyPilot (Agent + Tracker + Chromium) ────────────
FROM python:3.12-slim

# Install system deps for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (agent + tracker backend)
COPY requirements.txt ./agent-requirements.txt
COPY tracker/backend/requirements.txt ./tracker-requirements.txt
RUN pip install --no-cache-dir -r agent-requirements.txt -r tracker-requirements.txt

# Install Playwright + Chromium
RUN pip install --no-cache-dir playwright && playwright install chromium

# Copy the full agent source
COPY linkedin_agent/ ./linkedin_agent/
COPY config.yaml ./
COPY .env.example ./.env.example

# Copy tracker backend
COPY tracker/backend/ ./tracker/backend/

# Copy built frontend into tracker's static directory
COPY --from=frontend-build /app/frontend/dist ./tracker/backend/static

# Create data directories
RUN mkdir -p /app/data /app/logs /app/screenshots

# Set environment
ENV DATABASE_URL=sqlite:///./data/tracker.db
ENV PYTHONPATH=/app
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

EXPOSE 8000

# Start the tracker backend (which can trigger the agent)
WORKDIR /app/tracker/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

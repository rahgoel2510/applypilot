# ─── Stage 1: Build React Frontend ────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY tracker/frontend/package.json tracker/frontend/package-lock.json ./
RUN npm ci
COPY tracker/frontend/ ./
RUN npm run build


# ─── Stage 2: Full ApplyPilot (Agent + Tracker + Chromium) ────────────
FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

USER root
ENV HOME=/root
WORKDIR /app

# Install Python dependencies (agent + tracker backend)
COPY requirements.txt ./agent-requirements.txt
COPY tracker/backend/requirements.txt ./tracker-requirements.txt
RUN pip install --no-cache-dir --break-system-packages \
    -r agent-requirements.txt -r tracker-requirements.txt

# Copy the full agent source
COPY linkedin_agent/ ./linkedin_agent/
COPY config.yaml ./
COPY .env.example ./.env.example

# Copy tracker backend
COPY tracker/backend/ ./tracker/backend/

# Copy built frontend into tracker's static directory
COPY --from=frontend-build /app/frontend/dist ./tracker/backend/static

# Create data directories
RUN mkdir -p /app/data /app/logs /app/screenshots \
    /root/.local/share/linkedin_agent/browser_data

# Set environment
ENV DATABASE_URL=sqlite:///./data/tracker.db
ENV PYTHONPATH=/app

EXPOSE 8000

# Start the tracker backend (which can trigger the agent)
WORKDIR /app/tracker/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

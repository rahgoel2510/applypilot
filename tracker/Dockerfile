# ─── Stage 1: Build React Frontend ────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY tracker/frontend/package.json tracker/frontend/package-lock.json ./
RUN npm ci
COPY tracker/frontend/ ./
RUN npm run build


# ─── Stage 2: Python Backend + Static Frontend ────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install backend dependencies
COPY tracker/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY tracker/backend/ ./

# Copy built frontend into static directory
COPY --from=frontend-build /app/frontend/dist ./static

# Create data directory for SQLite
RUN mkdir -p /app/data

ENV DATABASE_URL=sqlite:///./data/tracker.db

EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

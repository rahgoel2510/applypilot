@echo off
:: ═══════════════════════════════════════════════════════════
:: ApplyPilot — Start (Windows)
:: ═══════════════════════════════════════════════════════════
:: 1. Starts the tracker (Docker) at http://localhost:8000
:: 2. Runs the agent natively (uses your LinkedIn session)
:: ═══════════════════════════════════════════════════════════

echo.
echo  ╔═══════════════════════════════════════╗
echo  ║   ApplyPilot — Powered by Rahul      ║
echo  ╚═══════════════════════════════════════╝
echo.

:: Start tracker
echo [1/2] Starting tracker (Docker)...
docker-compose up -d
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker failed. Is Docker Desktop running?
    pause
    exit /b 1
)
echo      Tracker: http://localhost:8000
echo.

:: Wait for tracker to be ready
timeout /t 3 /nobreak >nul

:: Run agent
echo [2/2] Starting agent (native — uses your LinkedIn session)...
echo      Mode: dry-run, Limit: 10 jobs
echo      Press Ctrl+C to stop
echo.
python -m linkedin_agent run --dry-run --limit 10

echo.
echo Done. Check http://localhost:8000 for results.
pause

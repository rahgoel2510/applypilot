"""FastAPI application for Job Application Tracker."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import Base, engine
from routes import router
from settings_routes import router as settings_router
from scheduler_routes import router as scheduler_router
from service_routes import router as service_router
from agents_routes import router as agents_router
from websocket_routes import router as ws_router
from todo_routes import router as todo_router
from privacy_routes import router as privacy_router
from audit_log import router as audit_router, AuditEntry, ConsentRecord  # noqa: F401
from health_routes import router as health_router
from models import Job, ActivityLog, AppSetting, AgentRun, FeedbackSignal, InMailDraft, Todo  # noqa: F401 — ensure models are registered before create_all

# Ensure all tables exist (covers test/import scenarios where lifespan may not fire)
Base.metadata.create_all(bind=engine)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup + cleanup orphaned runs."""
    Base.metadata.create_all(bind=engine)

    # Fix any runs stuck as "running" from previous crashes/restarts
    try:
        from database import SessionLocal
        from datetime import datetime
        db = SessionLocal()
        orphaned = db.query(AgentRun).filter(AgentRun.status == "running").all()
        for run in orphaned:
            run.status = "stopped"
            run.finished_at = run.finished_at or datetime.now()
            run.error_message = run.error_message or "Process terminated (server restarted)"
        if orphaned:
            db.commit()
        db.close()
    except Exception:
        pass

    # Start background data retention cleanup scheduler
    from cleanup_scheduler import start_cleanup_scheduler
    start_cleanup_scheduler()

    yield


app = FastAPI(
    title="Job Application Tracker",
    description="Track job applications across stages with LinkedIn agent integration.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware — restrict to known origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:80",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:80",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

from request_tracing import request_tracing_middleware
app.middleware("http")(request_tracing_middleware)

from security_headers import security_headers_middleware
app.middleware("http")(security_headers_middleware)

from auth_middleware import api_key_middleware
app.middleware("http")(api_key_middleware)

from rate_limiter import limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from metrics import metrics_middleware, metrics_route
app.middleware("http")(metrics_middleware)

# Include API routes
app.include_router(router)
app.include_router(settings_router)
app.include_router(scheduler_router)
app.include_router(service_router)
app.include_router(agents_router)
app.include_router(ws_router)
app.include_router(todo_router)
app.include_router(privacy_router)
app.include_router(audit_router)
app.include_router(health_router)

from cleanup_scheduler import cleanup_router
app.include_router(cleanup_router)

app.routes.append(metrics_route)


# Serve static frontend (when running in Docker with built assets)
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA for any non-API route."""
        # Don't intercept API routes
        if full_path.startswith("api"):
            return None
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
else:

    @app.get("/")
    def root():
        """Health check endpoint (dev mode, no static files)."""
        return {"status": "ok", "service": "Job Application Tracker"}

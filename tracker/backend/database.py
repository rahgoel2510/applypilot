"""Database configuration for Job Application Tracker."""

import os
import time

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool, StaticPool

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///./tracker.db')

# Use QueuePool for SQLite to get connection pooling benefits
if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(
        DATABASE_URL,
        connect_args={'check_same_thread': False},
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
    )
else:
    # PostgreSQL or other databases
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    """Enable WAL mode and performance pragmas on every new connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_health() -> dict:
    """Check database connectivity and return health metrics."""
    try:
        start = time.time()
        with engine.connect() as conn:
            # Basic connectivity check
            conn.execute(text("SELECT 1"))
            response_time_ms = round((time.time() - start) * 1000, 2)

            # SQLite PRAGMA info
            journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            page_count = conn.execute(text("PRAGMA page_count")).scalar()
            freelist_count = conn.execute(text("PRAGMA freelist_count")).scalar()

        pool = engine.pool
        return {
            "status": "healthy",
            "response_time_ms": response_time_ms,
            "journal_mode": journal_mode,
            "page_count": page_count,
            "freelist_count": freelist_count,
            "connection_pool_size": pool.size(),
            "connection_pool_overflow": pool.overflow(),
            "error": None,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "response_time_ms": None,
            "journal_mode": None,
            "page_count": None,
            "freelist_count": None,
            "connection_pool_size": None,
            "connection_pool_overflow": None,
            "error": str(e),
        }

"""Consent tracking and audit log for ApplyPilot."""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import Session

from database import Base, get_db


# ===========================================================================
# SQLAlchemy Models
# ===========================================================================


class AuditEntry(Base):
    __tablename__ = "audit_log"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    actor = Column(String, nullable=False)  # 'user', 'agent', 'system'
    action = Column(String, nullable=False)  # 'read', 'write', 'delete', 'export', 'login', 'consent_given', 'consent_revoked'
    resource_type = Column(String, nullable=False)  # jobs, settings, privacy, agent, etc.
    resource_id = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    details = Column(Text, nullable=True)  # JSON string with extra context


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    consent_type = Column(String, nullable=False)  # 'data_processing', 'automated_applications', 'profile_sharing'
    granted = Column(Boolean, default=True, nullable=False)
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)


# ===========================================================================
# Helper Functions
# ===========================================================================


def log_audit(
    db: Session,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[str] = None,
) -> AuditEntry:
    """Create an audit log entry."""
    entry = AuditEntry(
        id=str(uuid.uuid4()),
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        details=details,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def log_data_access(
    request: Request,
    db: Session,
    resource_type: str,
    resource_id: Optional[str] = None,
) -> AuditEntry:
    """Log a data access event, automatically extracting IP from the request."""
    ip_address = request.client.host if request.client else None
    return log_audit(
        db=db,
        actor="user",
        action="read",
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
    )


# ===========================================================================
# Pydantic Schemas
# ===========================================================================


class ConsentCreate(BaseModel):
    consent_type: str
    granted: bool = True


class AuditEntryResponse(BaseModel):
    id: str
    timestamp: datetime
    actor: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: Optional[str] = None

    class Config:
        from_attributes = True


class ConsentRecordResponse(BaseModel):
    id: str
    consent_type: str
    granted: bool
    granted_at: datetime
    revoked_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    class Config:
        from_attributes = True


# ===========================================================================
# API Routes
# ===========================================================================

router = APIRouter(tags=["audit"])


@router.get("/api/audit/logs")
def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get paginated audit log entries."""
    total = db.query(AuditEntry).count()
    logs = (
        db.query(AuditEntry)
        .order_by(AuditEntry.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "logs": [AuditEntryResponse.model_validate(log) for log in logs],
        "total": total,
        "page": page,
    }


@router.get("/api/consent", response_model=list[ConsentRecordResponse])
def get_consent_records(db: Session = Depends(get_db)):
    """List all consent records."""
    records = db.query(ConsentRecord).order_by(ConsentRecord.granted_at.desc()).all()
    return records


@router.post("/api/consent", response_model=ConsentRecordResponse, status_code=200)
def create_or_update_consent(
    payload: ConsentCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create or update a consent record."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Check if consent of this type already exists
    existing = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.consent_type == payload.consent_type)
        .filter(ConsentRecord.revoked_at.is_(None))
        .first()
    )

    if existing:
        # Update existing consent
        existing.granted = payload.granted
        existing.ip_address = ip_address
        existing.user_agent = user_agent
        if not payload.granted:
            existing.revoked_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        # Log audit
        action = "consent_given" if payload.granted else "consent_revoked"
        log_audit(db, "user", action, "privacy", existing.id, ip_address)
        return existing
    else:
        # Create new consent record
        record = ConsentRecord(
            id=str(uuid.uuid4()),
            consent_type=payload.consent_type,
            granted=payload.granted,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        if not payload.granted:
            record.revoked_at = datetime.utcnow()
        db.add(record)
        db.commit()
        db.refresh(record)
        # Log audit
        action = "consent_given" if payload.granted else "consent_revoked"
        log_audit(db, "user", action, "privacy", record.id, ip_address)
        return record


@router.delete("/api/consent/{consent_type}")
def revoke_consent(
    consent_type: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Revoke a consent by type."""
    ip_address = request.client.host if request.client else None

    record = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.consent_type == consent_type)
        .filter(ConsentRecord.revoked_at.is_(None))
        .first()
    )

    if not record:
        return {"detail": "No active consent found for this type"}

    record.granted = False
    record.revoked_at = datetime.utcnow()
    db.commit()

    log_audit(db, "user", "consent_revoked", "privacy", record.id, ip_address)

    return {"detail": f"Consent '{consent_type}' revoked", "revoked_at": record.revoked_at.isoformat()}

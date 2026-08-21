"""
Samvaadhika - SQLAlchemy ORM models.
Single SQLite file stores users, jobs, glossary, and audit log.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, Float, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from app.database import Base


def _uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False)
    full_name = Column(String(128), nullable=True)
    hashed_password = Column(String(256), nullable=False)
    role = Column(Enum("admin", "user", name="user_role"), default="user", nullable=False)
    is_active = Column(Boolean, default=True)
    is_approved = Column(Boolean, default=False)  # Admin must approve new accounts
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    jobs = relationship("Job", back_populates="owner", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username} [{self.role}]>"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Input metadata
    job_type = Column(
        Enum("text", "audio", "video", "document", name="job_type"),
        nullable=False
    )
    source_language = Column(String(8), nullable=True)   # auto-detected or user-set
    target_language = Column(String(8), nullable=False)
    input_filename = Column(String(256), nullable=True)
    input_path = Column(String(512), nullable=True)
    input_hash = Column(String(64), nullable=True, index=True)  # SHA-256 for dedup
    input_text = Column(Text, nullable=True)                    # for text jobs

    # Status
    status = Column(
        Enum("queued", "processing", "completed", "failed", name="job_status"),
        default="queued",
        nullable=False,
        index=True,
    )
    progress = Column(Integer, default=0)   # 0-100
    error_message = Column(Text, nullable=True)

    # Output
    output_path = Column(String(512), nullable=True)
    output_text = Column(Text, nullable=True)
    subtitle_path = Column(String(512), nullable=True)
    audio_output_path = Column(String(512), nullable=True)

    # Quality / confidence
    confidence_score = Column(Float, nullable=True)
    needs_review = Column(Boolean, default=False)
    review_notes = Column(Text, nullable=True)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="jobs")

    def __repr__(self):
        return f"<Job {self.id[:8]} [{self.job_type}] {self.status}>"


class GlossaryEntry(Base):
    """Domain-specific term overrides — agricultural/veterinary/BAIF program names."""
    __tablename__ = "glossary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_term = Column(String(256), nullable=False, index=True)
    source_language = Column(String(8), nullable=False)
    target_term = Column(String(256), nullable=False)
    target_language = Column(String(8), nullable=False)
    domain = Column(String(64), nullable=True)   # e.g. "agriculture", "veterinary"
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Glossary {self.source_term} → {self.target_term}>"


class AuditLog(Base):
    """Immutable audit trail — who translated what and when."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String(64), nullable=False)   # e.g. "translate_text", "upload_file"
    detail = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_id} at {self.timestamp}>"

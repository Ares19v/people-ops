import enum
import uuid
from datetime import datetime, date, timezone
from sqlalchemy import (
    Column, String, Boolean, Float, Date, DateTime, ForeignKey, Text, Enum
)
from sqlalchemy.orm import relationship
from app.core.database import Base

class TimesheetStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, index=True, nullable=False)
    client_name = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    entries = relationship("TimesheetEntry", back_populates="project")

class TimesheetEntry(Base):
    __tablename__ = "timesheet_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    task_name = Column(String(200), nullable=False)
    entry_date = Column(Date, nullable=False, index=True)
    hours = Column(Float, nullable=False)
    is_billable = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    status = Column(Enum(TimesheetStatus), default=TimesheetStatus.SUBMITTED, nullable=False)
    approver_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="timesheet_entries", foreign_keys=[user_id])
    project = relationship("Project", back_populates="entries")
    approver = relationship("User", foreign_keys=[approver_id])

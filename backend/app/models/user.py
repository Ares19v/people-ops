import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text, JSON, Enum, Float
)
from sqlalchemy.orm import relationship
from app.core.database import Base

class UserRole(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    HR_ASSOCIATE = "HR_ASSOCIATE"
    HR_MANAGER = "HR_MANAGER"
    ADMIN = "ADMIN"

class OnboardingStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    EXTRACTED_AWAITING_REVIEW = "EXTRACTED_AWAITING_REVIEW"
    COMPLETED = "COMPLETED"

class DocumentType(str, enum.Enum):
    AADHAAR = "AADHAAR"
    PAN = "PAN"
    RESUME = "RESUME"
    OTHER = "OTHER"

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.EMPLOYEE, nullable=False)
    department = Column(String(100), default="Engineering")
    designation = Column(String(100), default="Software Engineer")
    manager_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    manager = relationship("User", remote_side=[id], backref="direct_reports")
    profile = relationship("EmployeeProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", foreign_keys="Document.user_id")
    leave_balances = relationship("LeaveBalance", back_populates="user")
    leave_applications = relationship("LeaveApplication", back_populates="user", foreign_keys="LeaveApplication.user_id")
    timesheet_entries = relationship("TimesheetEntry", back_populates="user", foreign_keys="TimesheetEntry.user_id")

class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    date_of_birth = Column(String(20), nullable=True)
    address_encrypted = Column(Text, nullable=True)
    phone_encrypted = Column(Text, nullable=True)
    skills = Column(JSON, default=list) # List of skill strings
    experience_years = Column(Float, default=0.0)
    employment_type = Column(String(50), default="Full-Time Permanent")
    onboarding_status = Column(Enum(OnboardingStatus), default=OnboardingStatus.PENDING)
    extracted_resume_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="profile")

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    doc_type = Column(Enum(DocumentType), nullable=False)
    file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(Float, default=0)
    checksum = Column(String(64), nullable=True)
    is_verified = Column(Boolean, default=False)
    verified_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="documents", foreign_keys=[user_id])
    verifier = relationship("User", foreign_keys=[verified_by_id])

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False) # e.g. "LEAVE_APPLY", "TIMESHEET_APPROVE", "ONBOARDING_VERIFY"
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    actor = relationship("User")

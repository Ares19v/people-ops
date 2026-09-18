import enum
import uuid
from datetime import datetime, date, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Date, DateTime, ForeignKey, Text, Enum
)
from sqlalchemy.orm import relationship
from app.core.database import Base

class LeaveType(str, enum.Enum):
    EL = "EL"  # Earned Leave
    CL = "CL"  # Casual Leave
    SL = "SL"  # Sick Leave
    LWP = "LWP" # Leave Without Pay

class LeaveStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    year = Column(Integer, nullable=False, default=2026)
    leave_type = Column(Enum(LeaveType), nullable=False)
    total_allocated = Column(Float, default=0.0)
    used_days = Column(Float, default=0.0)
    pending_days = Column(Float, default=0.0)
    carry_forwarded = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="leave_balances")

    @property
    def available_balance(self) -> float:
        if self.leave_type == LeaveType.LWP:
            return 999.0 # LWP is uncapped
        return max(0.0, (self.total_allocated + self.carry_forwarded) - (self.used_days + self.pending_days))

class LeaveApplication(Base):
    __tablename__ = "leave_applications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    leave_type = Column(Enum(LeaveType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    total_days = Column(Float, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(Enum(LeaveStatus), default=LeaveStatus.SUBMITTED, nullable=False)
    approver_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    approver_comments = Column(Text, nullable=True)
    applied_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    decided_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="leave_applications", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approver_id])

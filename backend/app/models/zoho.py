"""
PeopleOps — Zoho People HRMS Ledger & Synchronization ORM Models
================================================================
Stores external synchronization ledger records, attendance syncs,
and inbound webhook audit logs for seamless HRMS synchronization.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, JSON, Text, Boolean
from app.core.database import Base


class ZohoSyncRecord(Base):
    __tablename__ = "zoho_sync_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    record_type = Column(String(50), nullable=False, index=True)  # ATTENDANCE, LEAVE_SYNC, PROFILE_SYNC
    zoho_record_id = Column(String(100), nullable=True, index=True)
    status = Column(String(50), default="SUCCESS", nullable=False)
    sync_payload = Column(JSON, nullable=True)
    sync_response = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "record_type": self.record_type,
            "zoho_record_id": self.zoho_record_id,
            "status": self.status,
            "sync_payload": self.sync_payload,
            "sync_response": self.sync_response,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

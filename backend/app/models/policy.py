import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, JSON, Enum
from app.core.database import Base

class PolicyStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_LEGAL_REVIEW = "PENDING_LEGAL_REVIEW"
    ACTIVE_APPROVED = "ACTIVE_APPROVED"
    ARCHIVED = "ARCHIVED"

class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    document_type = Column(String(50), default="COMPANY_POLICY") # STATUTORY_LAW or COMPANY_POLICY
    jurisdiction = Column(String(100), default="Maharashtra, India")
    status = Column(Enum(PolicyStatus), default=PolicyStatus.ACTIVE_APPROVED, nullable=False)
    reviewed_by = Column(String(255), nullable=True)
    raw_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), nullable=False)
    section_title = Column(String(255), nullable=False)
    citation = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    # Stored embedding (as JSON list for cross-DB compatibility, or pgvector in Postgres)
    embedding_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

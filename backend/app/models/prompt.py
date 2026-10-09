"""SQLAlchemy model for database-backed agent prompt storage, versioning, and Langfuse synchronization."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, DateTime, Text, Integer, Boolean
)
from app.core.database import Base


class AgentPrompt(Base):
    __tablename__ = "agent_prompts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prompt_key = Column(String(100), unique=True, nullable=False, index=True)
    agent_name = Column(String(100), nullable=False)
    template = Column(Text, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    label = Column(String(50), default="production", nullable=False)
    langfuse_version = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            "id": self.id,
            "prompt_key": self.prompt_key,
            "agent_name": self.agent_name,
            "template": self.template,
            "version": self.version,
            "label": self.label,
            "langfuse_version": self.langfuse_version,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

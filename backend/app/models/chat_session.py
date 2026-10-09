"""SQLAlchemy models for PostgreSQL/SQLite Conversational Session, Turn Checkpointing & Rolling Summaries."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, JSON, Integer
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(64), primary_key=True)  # session_id e.g. sess_xxx
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(255), default="HR Conversation")
    active_slots = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="chat_sessions")
    turns = relationship(
        "ChatTurn",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatTurn.created_at"
    )
    summaries = relationship(
        "ConversationSummary",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ConversationSummary.created_at.desc()"
    )


class ChatTurn(Base):
    __tablename__ = "chat_turns"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    turn_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    session = relationship("ChatSession", back_populates="turns")


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    covers_turns_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    session = relationship("ChatSession", back_populates="summaries")

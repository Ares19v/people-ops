"""Multi-Turn Conversational Memory & Persistent Entity State Manager.

Ensures the agent fleet 'remembers' context across sequential turns
(e.g., active leave dates, previous questions, ongoing multi-step workflows).
Features persistent snapshot backing, automatic entity extraction, and episodic search.
"""

from dataclasses import dataclass, field
import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.security import mask_all_pii
from app.models.chat_session import ChatSession, ChatTurn


@dataclass
class MemoryTurn:
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryTurn":
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {})
        )

class ConversationMemoryManager:
    """Thread-safe persistent session memory manager providing sliding-window history and entity memory."""

    def __init__(self, max_turns_per_session: int = 20, ttl_seconds: int = 86400):
        self._history: Dict[str, List[MemoryTurn]] = {}
        self._entities: Dict[str, Dict[str, Any]] = {}  # session_id -> {active_leave_type, days, etc.}
        self._last_accessed: Dict[str, float] = {}
        self._max_turns = max_turns_per_session
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._persistence_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data",
            "conversation_sessions.json"
        )
        self._load_from_disk()

    def _load_from_disk(self):
        """Restores persisted sessions on application startup."""
        if os.path.exists(self._persistence_file):
            try:
                with open(self._persistence_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    with self._lock:
                        for sid, turns in data.get("history", {}).items():
                            self._history[sid] = [MemoryTurn.from_dict(t) for t in turns]
                            self._last_accessed[sid] = time.time()
                        self._entities = data.get("entities", {})
            except Exception as e:
                print(f"Notice: Failed to load conversation memory from disk: {e}")

    def _save_to_disk(self):
        """Asynchronously or synchronously flushes active sessions to disk."""
        try:
            os.makedirs(os.path.dirname(self._persistence_file), exist_ok=True)
            export_data = {
                "history": {
                    sid: [t.to_dict() for t in turns]
                    for sid, turns in self._history.items()
                },
                "entities": self._entities,
                "saved_at": time.time()
            }
            with open(self._persistence_file, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
        except Exception as e:
            print(f"Notice: Failed to persist conversation memory: {e}")

    def add_turn(self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Appends a new turn to session history, ensuring zero raw PII storage and auto-updating entity states."""
        scrubbed = mask_all_pii(content)
        turn = MemoryTurn(role=role, content=scrubbed, metadata=metadata or {})

        with self._lock:
            if session_id not in self._history:
                self._history[session_id] = []
                self._entities[session_id] = {}

            self._history[session_id].append(turn)
            self._last_accessed[session_id] = time.time()

            # Automatic Entity Context Extraction for User turns
            if role == "user":
                self._extract_entities_from_text(session_id, content)

            # Trim history to sliding window
            if len(self._history[session_id]) > self._max_turns:
                self._history[session_id] = self._history[session_id][-self._max_turns:]

            self._save_to_disk()

    def _extract_entities_from_text(self, session_id: str, text: str):
        """Heuristic and regex extraction of active leave or timesheet entities."""
        text_lower = text.lower()
        entities = self._entities.setdefault(session_id, {})

        # 1. Leave Type
        if "casual leave" in text_lower or "cl" in text_lower.split():
            entities["active_leave_type"] = "Casual Leave (CL)"
        elif "earned leave" in text_lower or "el" in text_lower.split():
            entities["active_leave_type"] = "Earned Leave (EL)"
        elif "sick leave" in text_lower or "sl" in text_lower.split():
            entities["active_leave_type"] = "Sick Leave (SL)"
        elif "lwp" in text_lower or "leave without pay" in text_lower:
            entities["active_leave_type"] = "Leave Without Pay (LWP)"

        # 2. Duration Days
        days_match = re.search(r"\b(\d+)\s*(?:day|days)\b", text_lower)
        if days_match:
            try:
                entities["active_duration_days"] = int(days_match.group(1))
            except ValueError:
                pass

        # 3. Starting Anchor
        if "from next monday" in text_lower:
            entities["active_start_date"] = "Next Monday"
        elif "tomorrow" in text_lower:
            entities["active_start_date"] = "Tomorrow"
        elif "next week" in text_lower:
            entities["active_start_date"] = "Next Week"

    def get_history(self, session_id: str, limit: int = 6) -> List[Dict[str, str]]:
        """Returns the recent turns formatted as list of {role, content}."""
        with self._lock:
            self._cleanup_expired_sessions()
            turns = self._history.get(session_id, [])
            return [{"role": t.role, "content": t.content} for t in turns[-limit:]]

    def get_formatted_history(self, session_id: str, limit: int = 6) -> str:
        """Returns formatted string of conversation history and active entity memory for LLM context injection."""
        with self._lock:
            turns = self._history.get(session_id, [])
            recent_turns = turns[-limit:] if turns else []
            entities = self._entities.get(session_id, {})

        if not recent_turns and not entities:
            return "No previous conversation history."

        formatted_lines = []
        if entities:
            entity_str = ", ".join([f"{k}: {v}" for k, v in entities.items()])
            formatted_lines.append(f"Active Entity Memory Context: [{entity_str}]")

        for t in recent_turns:
            prefix = "Employee" if t.role == "user" else "Assistant"
            formatted_lines.append(f"{prefix}: {t.content}")

        return "\n".join(formatted_lines)

    def search_episodic_memory(self, session_id: str, query: str) -> List[str]:
        """Searches past turns in the session for keywords to answer cross-turn inquiries."""
        query_words = set(query.lower().split())
        results = []
        with self._lock:
            turns = self._history.get(session_id, [])
            for t in turns:
                content_lower = t.content.lower()
                matched = [w for w in query_words if len(w) > 3 and w in content_lower]
                if matched:
                    results.append(f"[{t.role.upper()}]: {t.content}")
        return results

    def set_entity(self, session_id: str, key: str, value: Any):
        """Stores a contextual fact (e.g. pending_leave_type='SICK_LEAVE', start_date='2026-10-15')."""
        with self._lock:
            if session_id not in self._entities:
                self._entities[session_id] = {}
            self._entities[session_id][key] = value
            self._save_to_disk()

    def get_entity(self, session_id: str, key: str) -> Optional[Any]:
        with self._lock:
            return self._entities.get(session_id, {}).get(key)

    def get_all_entities(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            return self._entities.get(session_id, {}).copy()

    def clear_session(self, session_id: str):
        with self._lock:
            self._history.pop(session_id, None)
            self._entities.pop(session_id, None)
            self._last_accessed.pop(session_id, None)
            self._save_to_disk()

    def _cleanup_expired_sessions(self):
        """Internal sweep for sessions exceeding TTL."""
        now = time.time()
        expired = [sid for sid, ts in self._last_accessed.items() if now - ts > self._ttl_seconds]
        for sid in expired:
            self._history.pop(sid, None)
            self._entities.pop(sid, None)
            self._last_accessed.pop(sid, None)

    async def persist_turn_db(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: Optional[str],
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None
    ) -> MemoryTurn:
        """Persists turn to PostgreSQL chat_turns table and synchronizes ChatSession state."""
        # 1. Update in-memory and disk snapshot
        self.add_turn(session_id, role, content, metadata)

        # 2. Checkpoint to PostgreSQL
        try:
            stmt = select(ChatSession).filter(ChatSession.id == session_id)
            res = await db.execute(stmt)
            chat_sess = res.scalar_one_or_none()

            active_slots = self.get_all_entities(session_id)

            if not chat_sess:
                chat_sess = ChatSession(
                    id=session_id,
                    user_id=user_id,
                    title=title or (content[:60] + "..." if len(content) > 60 else content),
                    active_slots=active_slots
                )
                db.add(chat_sess)
                await db.flush()
            else:
                chat_sess.active_slots = active_slots

            scrubbed = mask_all_pii(content)
            db_turn = ChatTurn(
                session_id=session_id,
                role=role,
                content=scrubbed,
                turn_metadata=metadata or {}
            )
            db.add(db_turn)
            await db.commit()
        except Exception as e:
            await db.rollback()
            print(f"Notice: PostgreSQL checkpointing non-fatal exception: {e}")

        return MemoryTurn(role=role, content=mask_all_pii(content), metadata=metadata or {})

    async def load_session_from_db(self, db: AsyncSession, session_id: str) -> bool:
        """Loads historical turns and entity slots from PostgreSQL if not already in memory."""
        try:
            stmt = select(ChatSession).filter(ChatSession.id == session_id)
            res = await db.execute(stmt)
            chat_sess = res.scalar_one_or_none()
            if not chat_sess:
                return False

            turn_stmt = select(ChatTurn).filter(ChatTurn.session_id == session_id).order_by(ChatTurn.created_at.asc())
            turn_res = await db.execute(turn_stmt)
            db_turns = turn_res.scalars().all()

            with self._lock:
                self._history[session_id] = [
                    MemoryTurn(
                        role=t.role,
                        content=t.content,
                        timestamp=t.created_at.timestamp() if t.created_at else time.time(),
                        metadata=t.turn_metadata or {}
                    )
                    for t in db_turns
                ]
                if chat_sess.active_slots:
                    self._entities[session_id] = chat_sess.active_slots
                self._last_accessed[session_id] = time.time()
                self._save_to_disk()
            return True
        except Exception as e:
            print(f"Notice: Failed to load session from DB: {e}")
            return False

    async def get_history_async(self, session_id: str, db: Optional[AsyncSession] = None, limit: int = 10) -> List[Dict[str, str]]:
        """Asynchronously returns history, checking DB first if memory empty."""
        if db:
            with self._lock:
                in_mem = self._history.get(session_id)
            if not in_mem:
                await self.load_session_from_db(db, session_id)
        return self.get_history(session_id, limit=limit)

    async def clear_session_async(self, session_id: str, db: Optional[AsyncSession] = None):
        """Flushes session from DB, in-memory, and disk."""
        self.clear_session(session_id)
        if db:
            try:
                stmt = delete(ChatSession).filter(ChatSession.id == session_id)
                await db.execute(stmt)
                await db.commit()
            except Exception as e:
                await db.rollback()
                print(f"Notice: Failed to clear session from DB: {e}")

    async def get_user_sessions_db(self, db: AsyncSession, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns all past chat sessions for a user from PostgreSQL."""
        try:
            stmt = select(ChatSession).filter(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc()).limit(limit)
            res = await db.execute(stmt)
            sessions = res.scalars().all()
            return [
                {
                    "session_id": s.id,
                    "title": s.title,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                    "active_slots": s.active_slots or {}
                }
                for s in sessions
            ]
        except Exception as e:
            print(f"Notice: Failed to query user sessions from DB: {e}")
            return []

conversation_memory = ConversationMemoryManager()


"""Multi-Turn Conversational Memory & Persistent Entity State Manager with Rolling Summaries.

Ensures the agent fleet 'remembers' context across sequential turns
and across distinct conversation sessions via a 5-Session Sliding Window.
Features persistent snapshot backing, automatic entity extraction, episodic search,
and PostgreSQL database checkpointing with strict per-user privacy isolation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, and_, or_
from app.core.security import mask_all_pii
from app.models.chat_session import ChatSession, ChatTurn, ConversationSummary, SessionSummary


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
    """Thread-safe persistent session memory manager providing sliding-window history,
    rolling summaries, and cross-session memory integration with strict user isolation.
    """

    def __init__(self, max_turns_per_session: int = 20, ttl_seconds: int = 86400, summary_threshold: int = 4):
        self._history: Dict[str, List[MemoryTurn]] = {}
        self._entities: Dict[str, Dict[str, Any]] = {}  # session_id -> {active_leave_type, days, etc.}
        self._summaries: Dict[str, str] = {}            # session_id -> latest rolling summary text
        self._last_accessed: Dict[str, float] = {}
        self._max_turns = max_turns_per_session
        self._ttl_seconds = ttl_seconds
        self._summary_threshold = summary_threshold
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
                        self._summaries = data.get("summaries", {})
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
                "summaries": self._summaries,
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
        elif "from friday" in text_lower:
            entities["active_start_date"] = "Friday"

    def get_all_entities(self, session_id: str) -> Dict[str, Any]:
        """Returns all extracted slots/entities for the active session."""
        with self._lock:
            return dict(self._entities.get(session_id, {}))

    def get_entities(self, session_id: str) -> Dict[str, Any]:
        """Alias for get_all_entities."""
        return self.get_all_entities(session_id)

    def set_entity(self, session_id: str, key: str, value: Any):
        """Sets a slot/entity value for the active session."""
        with self._lock:
            if session_id not in self._entities:
                self._entities[session_id] = {}
            self._entities[session_id][key] = value
            self._save_to_disk()

    def clear_session(self, session_id: str):
        """Synchronously flushes session from in-memory cache and disk."""
        with self._lock:
            self._history.pop(session_id, None)
            self._entities.pop(session_id, None)
            self._summaries.pop(session_id, None)
            self._last_accessed.pop(session_id, None)
            self._save_to_disk()

    def get_turns(self, session_id: str) -> List[MemoryTurn]:
        """Returns all MemoryTurn objects recorded in the active session."""
        with self._lock:
            return list(self._history.get(session_id, []))

    def get_history(self, session_id: str, limit: int = 6) -> List[Dict[str, str]]:
        """Returns the recent turns formatted as list of {role, content}."""
        with self._lock:
            self._cleanup_expired_sessions()
            turns = self._history.get(session_id, [])
            return [{"role": t.role, "content": t.content} for t in turns[-limit:]]

    async def get_history_async(self, session_id: str, db: Optional[AsyncSession] = None, limit: int = 10) -> List[Dict[str, str]]:
        """Async loader retrieving turns from DB or memory snapshot."""
        if db:
            await self.load_session_from_db(db, session_id)
        return self.get_history(session_id, limit=limit)

    def get_formatted_history(
        self,
        session_id: str,
        limit: int = 6,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        user_name: Optional[str] = None,
        cross_session_summaries: Optional[List[Dict[str, Any]]] = None,
        recalled_turns: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Returns formatted string combining cross-session 5-window memory, identity context,
        recalled past dialogue turns, and current session recent turns.
        """
        with self._lock:
            turns = self._history.get(session_id, [])
            recent_turns = turns[-limit:] if turns else []
            entities = self._entities.get(session_id, {})
            current_summary = self._summaries.get(session_id)

        formatted_lines = []

        EMPLOYEE_NAME_MAP = {
            "EMP-001": "Devansh Tyagi",
            "EMP-002": "Vikram Malhotra",
            "EMP-003": "Priya Patel",
            "EMP-004": "Rahul Sharma",
            "EMP-005": "Sneha Kulkarni",
        }
        resolved_name = user_name
        if not resolved_name and user_id:
            resolved_name = EMPLOYEE_NAME_MAP.get(user_id.upper().strip())
        if not resolved_name and user_id:
            resolved_name = user_id

        # 1. Identity & Time Context Header
        if user_id:
            now_str = datetime.now(timezone.utc).strftime("%A, %B %d, %Y %I:%M %p UTC")
            first_name = resolved_name.split()[0] if resolved_name and " " in resolved_name else (resolved_name or "there")
            formatted_lines.append("════════════════════════════════════════════════════════════")
            formatted_lines.append(f"AUTHENTICATED EMPLOYEE: {resolved_name} (ID: {user_id}, Role: {user_role or 'EMPLOYEE'})")
            formatted_lines.append(f"CURRENT_TIME: {now_str}")
            formatted_lines.append(f"NAME DIRECTIVE: Always address the employee by their first name ('{first_name}'). NEVER greet or address the employee using their employee ID code (NEVER say 'EMP-004', 'EMP-001', or similar).")
            formatted_lines.append("════════════════════════════════════════════════════════════")

        # 2. CROSS-SESSION ROLLING MEMORY (5-Session Sliding Window)
        if cross_session_summaries and len(cross_session_summaries) > 0:
            formatted_lines.append("\n╔══════════════════════════════════════════════════════════╗")
            formatted_lines.append(f"║ CROSS-CONVERSATION MEMORY ({len(cross_session_summaries)}-Session Sliding Window)        ║")
            formatted_lines.append("╚══════════════════════════════════════════════════════════╝")
            formatted_lines.append("The employee previously had the following conversations with you:\n")
            
            has_pending = False
            for idx, s in enumerate(cross_session_summaries, 1):
                title = s.get("session_title") or f"Session {idx}"
                summary = s.get("summary_text", "")
                pending = s.get("pending_action")
                date_str = s.get("created_at", "")[:10] if s.get("created_at") else "Recent"
                
                formatted_lines.append(f"[{idx}. {title} ({date_str})]")
                formatted_lines.append(f"• Summary: {summary}")
                if pending and pending != "None" and pending.strip():
                    formatted_lines.append(f"• PENDING / UNFINISHED ACTION: {pending}")
                    has_pending = True
                formatted_lines.append("")

            formatted_lines.append("CROSS-SESSION MEMORY GUIDELINE:")
            formatted_lines.append("- You have access to the employee's past interactions for background context.")
            formatted_lines.append("- CRITICAL CONSTRAINT: DO NOT unpromptedly dump past conversation topics, saved personal facts, or unfinished requests when the employee is asking a general question, greeting you, or changing the subject.")
            formatted_lines.append("- ONLY bring up past conversations or unfinished actions when:")
            formatted_lines.append("  1. The employee explicitly asks about them or asks you to recall something (e.g. 'what were we discussing?', 'what was my pending request?', 'do you remember my pet/contact?'), OR")
            formatted_lines.append("  2. The employee's current query directly pertains to that specific pending task (e.g. they say 'submit that leave we talked about').")
            formatted_lines.append("- When the employee greets you or asks an unrelated question (e.g. 'hi whats going on in pune'), address their question/greeting directly and naturally without listing past chat history.")
            formatted_lines.append("────────────────────────────────────────────────────────────\n")

        # 3. RECALLED HISTORICAL EXCERPTS (Deep Episodic Memory Turn Retrieval)
        if recalled_turns and len(recalled_turns) > 0:
            formatted_lines.append("\n╔══════════════════════════════════════════════════════════╗")
            formatted_lines.append("║ EXACT RECALLED HISTORICAL EXCERPTS FROM PAST SESSIONS    ║")
            formatted_lines.append("╚══════════════════════════════════════════════════════════╝")
            formatted_lines.append("The employee specifically had the following exchange with you in a past session:\n")
            for r_idx, r in enumerate(recalled_turns, 1):
                sess_t = r.get("session_title") or r.get("session_id", "Past Conversation")
                date_s = r.get("date", "Earlier")
                u_turn = r.get("user_turn", "")
                a_turn = r.get("assistant_turn", "")
                formatted_lines.append(f"[{r_idx}. Conversation '{sess_t}' ({date_s})]")
                formatted_lines.append(f"• Employee: \"{u_turn}\"")
                if a_turn:
                    formatted_lines.append(f"• Assistant: \"{a_turn}\"")
                formatted_lines.append("")

            formatted_lines.append("CRITICAL MEMORY & RECALL INSTRUCTION:")
            formatted_lines.append("- The employee has discussed the topics in the excerpts above in past sessions.")
            formatted_lines.append("- If the employee asks about what they previously shared or asked, answer accurately and directly from these excerpts.")
            formatted_lines.append("- DO NOT regurgitate these excerpts unless they are directly relevant to what the employee is currently saying.")
            formatted_lines.append("- NEVER apologize or claim you cannot recall past conversations when relevant information is in the context.")
            formatted_lines.append("────────────────────────────────────────────────────────────\n")

        # 4. Current Session Rolling Summary if available
        if current_summary:
            formatted_lines.append("── Current Session In-Progress Summary ──")
            formatted_lines.append(current_summary)
            formatted_lines.append("──────────────────────────────────────────")

        # 5. Active Entities for current session
        if entities:
            entity_str = ", ".join([f"{k}: {v}" for k, v in entities.items()])
            formatted_lines.append(f"Active Session Entities: [{entity_str}]")

        # 6. Current Session Recent turns
        if recent_turns:
            formatted_lines.append("── Current Conversation Turns ──")
            for t in recent_turns:
                prefix = "Employee" if t.role == "user" else "Assistant"
                formatted_lines.append(f"{prefix}: {t.content}")
        else:
            formatted_lines.append("(No messages yet in this new session)")

        return "\n".join(formatted_lines)

    async def get_user_sliding_window_summaries(
        self,
        db: AsyncSession,
        user_id: str,
        current_session_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieves the latest 5 session summaries for this employee from PostgreSQL.
        Strictly user-scoped to guarantee zero cross-employee data leakage.
        """
        try:
            from app.observability.langsmith_tracer import resolve_user_email
            resolved_email = resolve_user_email(user_id)

            query = select(ConversationSummary).filter(
                (ConversationSummary.user_id == user_id) |
                (ConversationSummary.user_email == user_id) |
                (ConversationSummary.user_email == resolved_email)
            )
            if current_session_id:
                query = query.filter(ConversationSummary.session_id != current_session_id)
            
            query = query.order_by(ConversationSummary.created_at.desc()).limit(limit)
            res = await db.execute(query)
            summaries = res.scalars().all()

            # Reverse to chronological order (S_n-4 ... S_n) for the sliding window
            ordered = list(reversed(summaries))
            
            return [
                {
                    "id": s.id,
                    "session_id": s.session_id,
                    "session_title": s.session_title or "Conversation Session",
                    "summary_text": s.summary_text,
                    "pending_action": s.pending_action,
                    "key_entities": s.key_entities or {},
                    "status": s.status,
                    "created_at": s.created_at.isoformat() if s.created_at else None
                }
                for s in ordered
            ]
        except Exception as e:
            print(f"Notice: Failed to fetch sliding window summaries for user {user_id}: {e}")
            return []

    async def recall_relevant_past_turns(
        self,
        db: AsyncSession,
        user_id: str,
        current_session_id: str,
        query: str,
        recent_turns: Optional[List[Any]] = None,
        limit: int = 4
    ) -> List[Dict[str, Any]]:
        """Deep episodic recall across historical chat turns for this employee.
        Retrieves matching dialogue turns and their immediate assistant responses.
        Strictly user-scoped to guarantee zero cross-employee data leakage.
        """
        try:
            # 1. Collect candidate search words from query + recent current turns
            stop_words = {
                "what", "did", "say", "about", "my", "the", "a", "an", "is", "in", "past",
                "conversation", "conversations", "last", "remember", "told", "you", "already",
                "i", "we", "chat", "earlier", "can", "please", "me", "to", "for", "and",
                "or", "so", "that", "this", "do", "don't", "need", "start", "something",
                "new", "with", "proceed", "hello", "hi", "hey", "tell", "was", "were", "are",
                "there", "have", "had", "just", "like", "know", "then", "which", "some", "our"
            }
            combined_text = query.lower()
            if recent_turns:
                for rt in recent_turns[-3:]:
                    content = rt.content if hasattr(rt, "content") else (rt.get("content", "") if isinstance(rt, dict) else str(rt))
                    combined_text += " " + content.lower()

            words = re.findall(r"\b[a-zA-Z]{3,}\b", combined_text)
            tokens = [w for w in words if w not in stop_words]

            is_recall_query = any(k in query.lower() for k in [
                "remember", "past conversation", "previous conversation", "earlier",
                "told you", "told u", "last time", "last chat", "before", "recall",
                "mentioned", "said about", "we talked", "we spoke", "what is my",
                "where do i", "who is my", "which day", "what day", "which project",
                "what project", "my pet", "my emergency", "my wfh", "my manager", "my lead"
            ])

            # If no meaningful tokens and not a recall query, skip episodic scan
            if not tokens and not is_recall_query:
                return []

            # 2. Query historical turns for this user from OTHER sessions
            stmt = (
                select(ChatTurn, ChatSession.title, ChatSession.id)
                .join(ChatSession, ChatTurn.session_id == ChatSession.id)
                .filter(
                    ChatSession.user_id == user_id,
                    ChatSession.id != current_session_id
                )
                .order_by(ChatTurn.created_at.desc())
                .limit(300)
            )
            res = await db.execute(stmt)
            rows = res.all()
            if not rows:
                return []

            # Group turns by session (preserve recency order of sessions)
            session_turns: Dict[str, List[ChatTurn]] = {}
            session_titles: Dict[str, str] = {}
            recent_session_ids: List[str] = []
            for turn, title, sess_id in rows:
                if sess_id not in session_turns:
                    recent_session_ids.append(sess_id)
                session_turns.setdefault(sess_id, []).append(turn)
                session_titles[sess_id] = title or "Previous HR Conversation"

            top_5_sessions = set(recent_session_ids[:5])

            # 3. Score and find relevant turns
            matches = []
            for sess_id, s_turns in session_turns.items():
                s_turns_sorted = sorted(s_turns, key=lambda t: t.created_at if t.created_at else datetime.min)
                is_in_sliding_window = sess_id in top_5_sessions

                for i, t in enumerate(s_turns_sorted):
                    if t.role != "user":
                        continue
                    turn_text_lower = t.content.lower().strip()

                    score = 0
                    for token in tokens:
                        if token in turn_text_lower:
                            score += 4
                        elif token.endswith("s") and token[:-1] in turn_text_lower:
                            score += 3
                        elif (token + "s") in turn_text_lower:
                            score += 3

                    # Bonus for statement / fact / preference turns vs. question turns
                    if any(w in turn_text_lower for w in [
                        "my emergency", "priya", "sister", "thursdays", "thursday", "prefer",
                        "vikram", "lead", "manager", "live in", "stay in", "pune", "mumbai",
                        "bangalore", "pet", "vivan", "vivi", "project", "phoenix", "apollo",
                        "neck", "headache", "ergonomic", "fever", "sick", "casual leave", "hours"
                    ]):
                        score += 12
                    if is_in_sliding_window:
                        score += 5
                    if turn_text_lower.startswith(("who did", "what did", "did i tell", "can you remember", "summarize", "do you remember", "what is my", "where do i", "who is my")):
                        score -= 10

                    # If query is recall-specific or matches candidate tokens
                    if score > 0 or (is_recall_query and is_in_sliding_window):
                        assistant_reply = ""
                        if i + 1 < len(s_turns_sorted) and s_turns_sorted[i+1].role == "assistant":
                            assistant_reply = s_turns_sorted[i+1].content

                        date_str = t.created_at.strftime("%Y-%m-%d") if t.created_at else "Earlier"
                        matches.append({
                            "session_id": sess_id,
                            "session_title": session_titles.get(sess_id, "Previous Session"),
                            "user_turn": t.content,
                            "assistant_turn": assistant_reply,
                            "date": date_str,
                            "score": score if score > 0 else 1
                        })

            matches.sort(key=lambda m: m["score"], reverse=True)
            return matches[:max(limit, 6)]
        except Exception as e:
            print(f"Notice: Failed to recall past turns: {e}")
            return []

    async def generate_and_save_session_summary(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: Optional[str] = None,
        force: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Generates a structured session summary capturing intents, medical/personal details,
        decisions, entities, and any unfinished / pending action. Persists to PostgreSQL.
        """
        try:
            # 1. Fetch turns for this session
            stmt = select(ChatTurn).filter(ChatTurn.session_id == session_id).order_by(ChatTurn.created_at.asc())
            res = await db.execute(stmt)
            turns = res.scalars().all()

            if not turns or (len(turns) < 2 and not force):
                return None

            # Get ChatSession metadata
            sess_stmt = select(ChatSession).filter(ChatSession.id == session_id)
            sess_res = await db.execute(sess_stmt)
            chat_sess = sess_res.scalar_one_or_none()
            
            target_user_id = user_id or (chat_sess.user_id if chat_sess else None)
            session_title = chat_sess.title if chat_sess else "HR Conversation"

            # 2. Extract conversation dynamics
            user_messages = [t.content for t in turns if t.role == "user"]
            assistant_messages = [t.content for t in turns if t.role == "assistant"]
            all_text_lower = " ".join([t.content.lower() for t in turns])

            # Detect Domain & Pending Action
            pending_action: Optional[str] = None
            entities: Dict[str, Any] = chat_sess.active_slots if chat_sess and chat_sess.active_slots else {}

            # Detect pending action
            if any(w in all_text_lower for w in ["leave", "vacation", "pto", "cl", "el", "sl", "day off"]):
                if any(w in all_text_lower for w in ["apply", "take", "request", "need"]) and not any(w in all_text_lower for w in ["successfully applied", "application approved", "decision recorded", "leave submitted"]):
                    leave_type = entities.get("active_leave_type", "Leave")
                    duration = entities.get("active_duration_days", "")
                    duration_str = f" ({duration} days)" if duration else ""
                    pending_action = f"Unsubmitted {leave_type}{duration_str} request. Awaiting employee confirmation to submit."

            elif any(w in all_text_lower for w in ["timesheet", "hours", "overtime", "project", "billable"]):
                if any(w in all_text_lower for w in ["log", "record", "enter"]) and not any(w in all_text_lower for w in ["logged successfully", "timesheet entry submitted"]):
                    pending_action = "Draft timesheet entry was discussed but not finalized."

            # 3. Generate High-Fidelity Summary via LLM
            summary_text = ""
            try:
                from app.core.llm_bridge import generate_summary
                dialogue_text = "\n".join([f"{t.role.capitalize()}: {t.content}" for t in turns[-8:]])
                prompt = (
                    "Summarize this employee HR conversation in 2-3 concise sentences for memory retention across chats.\n"
                    "Crucial: Explicitly mention any medical reasons, physical conditions, or symptoms reported by the employee (e.g. eye redness, fever, pain, injury), "
                    "the specific leave or timesheet requested, advice given by the assistant, and whether the request was submitted or left pending.\n\n"
                    f"{dialogue_text}\n\n"
                    "Summary:"
                )
                llm_sum = await generate_summary(prompt)
                if llm_sum and not llm_sum.startswith("[MOCK SUMMARY]") and len(llm_sum) > 20:
                    summary_text = llm_sum.strip()
            except Exception as sum_exc:
                print(f"Notice: LLM summary generation fallback: {sum_exc}")

            # 4. Fallback intelligent heuristic if LLM unavailable
            if not summary_text:
                health_reasons = []
                for kw in ["red eye", "eye", "eyes", "fever", "headache", "cold", "flu", "cough", "infection", "doctor", "hospital", "sick", "ill", "injury", "pain"]:
                    if kw in all_text_lower and kw not in health_reasons:
                        health_reasons.append(kw)

                substantive_msgs = [m for m in user_messages if len(m) > 4 and m.lower().strip() not in ["hi", "hello", "hey", "10", "test", "ok", "okay"]]
                primary_inquiry = substantive_msgs[0] if substantive_msgs else (user_messages[0] if user_messages else "general HR guidance")

                health_desc = f" (reporting: {', '.join(health_reasons)})" if health_reasons else ""
                summary_text = f"Employee discussed: \"{primary_inquiry[:120]}\"{health_desc}. Assistant provided guidance."
                if pending_action:
                    summary_text += f" Left off with: {pending_action}"
                else:
                    summary_text += " Action concluded."

            sess_suffix = session_id[5:] if session_id.startswith("sess_") else session_id
            summary_id = f"sum_{sess_suffix}"

            # 5. Upsert into PostgreSQL conversation_summaries
            find_stmt = select(ConversationSummary).filter(ConversationSummary.session_id == session_id)
            find_res = await db.execute(find_stmt)
            existing_summary = find_res.scalar_one_or_none()

            status_val = "ACTION_PENDING" if pending_action else "COMPLETED"

            from app.observability.langsmith_tracer import resolve_user_email
            user_email_val = resolve_user_email(target_user_id) if target_user_id else (chat_sess.user_email if chat_sess else None)

            if existing_summary:
                existing_summary.summary_text = summary_text
                existing_summary.session_title = session_title
                existing_summary.key_entities = entities
                existing_summary.pending_action = pending_action
                existing_summary.status = status_val
                existing_summary.covers_turns_count = len(turns)
                existing_summary.created_at = datetime.now(timezone.utc)
                if user_email_val:
                    existing_summary.user_email = user_email_val
                if target_user_id:
                    existing_summary.user_id = target_user_id
            else:
                new_summary = ConversationSummary(
                    id=summary_id,
                    session_id=session_id,
                    user_id=target_user_id,
                    user_email=user_email_val,
                    session_title=session_title,
                    summary_text=summary_text,
                    key_entities=entities,
                    pending_action=pending_action,
                    status=status_val,
                    covers_turns_count=len(turns)
                )
                db.add(new_summary)

            await db.commit()

            with self._lock:
                self._summaries[session_id] = summary_text
                self._save_to_disk()

            return {
                "id": summary_id,
                "session_id": session_id,
                "user_id": target_user_id,
                "user_email": user_email_val,
                "session_title": session_title,
                "summary_text": summary_text,
                "pending_action": pending_action,
                "status": status_val
            }
        except Exception as e:
            await db.rollback()
            print(f"Notice: Failed to generate and save session summary: {e}")
            return None

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

        # 2. Checkpoint to database
        try:
            stmt = select(ChatSession).filter(ChatSession.id == session_id)
            res = await db.execute(stmt)
            chat_sess = res.scalar_one_or_none()

            active_slots = self.get_all_entities(session_id)

            from app.observability.langsmith_tracer import resolve_user_email
            resolved_email = resolve_user_email(user_id) if user_id else None

            if not chat_sess:
                # Generate clean human-readable title from first user query
                first_title = title or (content[:60] + "..." if len(content) > 60 else content)
                chat_sess = ChatSession(
                    id=session_id,
                    user_id=user_id,
                    user_email=resolved_email,
                    title=first_title,
                    active_slots=active_slots
                )
                db.add(chat_sess)
                await db.flush()
            else:
                chat_sess.active_slots = active_slots
                chat_sess.updated_at = datetime.now(timezone.utc)
                if user_id and not chat_sess.user_id:
                    chat_sess.user_id = user_id
                if resolved_email and not chat_sess.user_email:
                    chat_sess.user_email = resolved_email

            with self._lock:
                turns_count = len(self._history.get(session_id, []))

            sess_name = session_id[5:] if session_id.startswith("sess_") else session_id
            turn_id = f"turn_{sess_name}_{turns_count}"
            scrubbed = mask_all_pii(content)
            db_turn = ChatTurn(
                id=turn_id,
                session_id=session_id,
                role=role,
                content=scrubbed,
                turn_metadata=metadata or {}
            )
            db.add(db_turn)
            await db.commit()

            # Auto-update summary only after assistant completes a turn pair
            if role == "assistant" and turns_count >= 2:
                await self.generate_and_save_session_summary(db, session_id, user_id=user_id)

        except Exception as e:
            await db.rollback()
            print(f"Notice: Database checkpointing non-fatal exception: {e}")

        return MemoryTurn(role=role, content=mask_all_pii(content), metadata=metadata or {})

    async def load_session_from_db(self, db: AsyncSession, session_id: str) -> bool:
        """Loads historical turns, rolling summary, and entity slots from DB if not already in memory."""
        try:
            stmt = select(ChatSession).filter(ChatSession.id == session_id)
            res = await db.execute(stmt)
            chat_sess = res.scalar_one_or_none()
            if not chat_sess:
                return False

            turn_stmt = select(ChatTurn).filter(ChatTurn.session_id == session_id).order_by(ChatTurn.created_at.asc())
            turn_res = await db.execute(turn_stmt)
            db_turns = turn_res.scalars().all()

            # Load latest summary if exists
            summary_stmt = select(ConversationSummary).filter(
                ConversationSummary.session_id == session_id
            ).order_by(ConversationSummary.created_at.desc()).limit(1)
            summary_res = await db.execute(summary_stmt)
            latest_summary = summary_res.scalar_one_or_none()

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
                if latest_summary:
                    self._summaries[session_id] = latest_summary.summary_text
                self._last_accessed[session_id] = time.time()
                self._save_to_disk()
            return True
        except Exception as e:
            print(f"Notice: Failed to load session from DB: {e}")
            return False

    async def clear_session_async(self, session_id: str, db: Optional[AsyncSession] = None):
        """Flushes session from DB, in-memory, and disk."""
        with self._lock:
            self._history.pop(session_id, None)
            self._entities.pop(session_id, None)
            self._summaries.pop(session_id, None)
            self._last_accessed.pop(session_id, None)
            self._save_to_disk()

        if db:
            try:
                stmt = delete(ChatSession).filter(ChatSession.id == session_id)
                await db.execute(stmt)
                await db.commit()
            except Exception as e:
                await db.rollback()
                print(f"Notice: Failed to clear session from DB: {e}")

    async def get_user_sessions_db(self, db: AsyncSession, user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Returns all past chat sessions for a specific user from PostgreSQL.
        Strictly user-scoped to prevent unauthorized cross-employee viewing.
        """
        try:
            from app.observability.langsmith_tracer import resolve_user_email
            resolved_email = resolve_user_email(user_id)

            stmt = select(ChatSession).filter(
                (ChatSession.user_id == user_id) |
                (ChatSession.user_email == user_id) |
                (ChatSession.user_email == resolved_email)
            ).order_by(ChatSession.updated_at.desc()).limit(limit)
            
            res = await db.execute(stmt)
            sessions = res.scalars().all()

            results = []
            for s in sessions:
                # Count turns
                cnt_stmt = select(func.count(ChatTurn.id)).filter(ChatTurn.session_id == s.id)
                cnt_res = await db.execute(cnt_stmt)
                turns_count = cnt_res.scalar() or 0

                # Fetch summary status
                sum_stmt = select(ConversationSummary).filter(
                    ConversationSummary.session_id == s.id
                ).order_by(ConversationSummary.created_at.desc()).limit(1)
                sum_res = await db.execute(sum_stmt)
                latest_sum = sum_res.scalar_one_or_none()

                results.append({
                    "id": s.id,
                    "session_id": s.id,
                    "user_id": s.user_id,
                    "user_email": s.user_email or resolved_email,
                    "title": s.title or "Conversation Session",
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                    "turns_count": turns_count,
                    "message_count": turns_count,
                    "pending_action": latest_sum.pending_action if latest_sum else None,
                    "summary_snippet": (latest_sum.summary_text[:100] + "...") if (latest_sum and len(latest_sum.summary_text) > 100) else (latest_sum.summary_text if latest_sum else None),
                    "active_slots": s.active_slots or {}
                })
            return results
        except Exception as e:
            print(f"Notice: Failed to query user sessions from DB: {e}")
            return []

    async def delete_user_session_db(self, db: AsyncSession, session_id: str, user_id: str) -> bool:
        """Securely deletes a session owned by this specific user from PostgreSQL and memory."""
        try:
            stmt = select(ChatSession).filter(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id
            )
            res = await db.execute(stmt)
            chat_sess = res.scalar_one_or_none()
            if not chat_sess:
                return False

            await db.execute(delete(ChatTurn).filter(ChatTurn.session_id == session_id))
            await db.execute(delete(ConversationSummary).filter(ConversationSummary.session_id == session_id))
            await db.delete(chat_sess)
            await db.commit()

            with self._lock:
                self._history.pop(session_id, None)
                self._entities.pop(session_id, None)
                self._summaries.pop(session_id, None)
                self._last_accessed.pop(session_id, None)
                self._save_to_disk()

            try:
                from app.agents.adk_fleet import get_default_hr_runner
                runner = get_default_hr_runner()
                runner.session_service.delete_session(
                    app_name=runner.app_name, user_id=user_id, session_id=session_id
                )
            except Exception:
                pass

            return True
        except Exception as e:
            await db.rollback()
            print(f"Notice: Failed to delete user session {session_id}: {e}")
            return False

    async def purge_user_chat_history_db(self, db: AsyncSession, user_id: str, user_email: Optional[str] = None) -> Dict[str, Any]:
        """Completely purges all chat sessions, turns, and conversation summaries for a user from PostgreSQL/SQLite and memory."""
        try:
            from app.observability.langsmith_tracer import resolve_user_email
            from app.core.id_generator import get_email_prefix
            resolved_email = user_email or resolve_user_email(user_id)
            prefix = get_email_prefix(resolved_email or user_id)

            # 1. Collect all session IDs belonging to this user
            stmt = select(ChatSession.id).filter(
                (ChatSession.user_id == user_id) |
                (ChatSession.user_email == user_id) |
                (ChatSession.user_email == resolved_email)
            )
            res = await db.execute(stmt)
            session_ids = [row[0] for row in res.fetchall()]

            # Also check session ID pattern
            pat_stmt = select(ChatSession.id).filter(ChatSession.id.like(f"sess_{prefix}_%"))
            res_p = await db.execute(pat_stmt)
            for row in res_p.fetchall():
                if row[0] not in session_ids:
                    session_ids.append(row[0])

            # 2. Delete all ChatTurn records
            if session_ids:
                del_turns = delete(ChatTurn).filter(ChatTurn.session_id.in_(session_ids))
                await db.execute(del_turns)

            # 3. Delete all ConversationSummary records
            conds = [
                ConversationSummary.user_id == user_id,
                ConversationSummary.user_email == resolved_email
            ]
            if session_ids:
                conds.append(ConversationSummary.session_id.in_(session_ids))
            del_sums = delete(ConversationSummary).filter(or_(*conds))
            await db.execute(del_sums)

            # 4. Delete all ChatSession records
            if session_ids:
                del_sess = delete(ChatSession).filter(ChatSession.id.in_(session_ids))
                await db.execute(del_sess)

            del_rem = delete(ChatSession).filter(
                (ChatSession.user_id == user_id) |
                (ChatSession.user_email == resolved_email)
            )
            await db.execute(del_rem)

            await db.commit()

            # 5. Clean up in-memory cache, disk snapshot, and ADK session service
            with self._lock:
                for sid in session_ids:
                    self._history.pop(sid, None)
                    self._entities.pop(sid, None)
                    self._summaries.pop(sid, None)
                    self._last_accessed.pop(sid, None)
                for sid in list(self._history.keys()):
                    if sid.startswith(f"sess_{prefix}_"):
                        self._history.pop(sid, None)
                        self._entities.pop(sid, None)
                        self._summaries.pop(sid, None)
                        self._last_accessed.pop(sid, None)
                self._save_to_disk()

            try:
                from app.agents.adk_fleet import get_default_hr_runner
                runner = get_default_hr_runner()
                for sid in session_ids:
                    try:
                        runner.session_service.delete_session(
                            app_name=runner.app_name, user_id=user_id, session_id=sid
                        )
                    except Exception:
                        pass
            except Exception:
                pass

            return {
                "status": "PURGED",
                "purged_sessions_count": len(session_ids),
                "user_id": user_id,
                "user_email": resolved_email
            }
        except Exception as e:
            await db.rollback()
            print(f"Notice: Failed to purge user chat history: {e}")
            raise

    def _cleanup_expired_sessions(self):
        """Internal sweep for sessions exceeding TTL."""
        now = time.time()
        expired = [sid for sid, ts in self._last_accessed.items() if now - ts > self._ttl_seconds]
        for sid in expired:
            self._history.pop(sid, None)
            self._entities.pop(sid, None)
            self._summaries.pop(sid, None)
            self._last_accessed.pop(sid, None)


conversation_memory = ConversationMemoryManager()

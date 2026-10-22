"""Live usage analytics (users, sessions, tokens, cost) computed from persisted chat turns.

Every assistant turn stores `agent_name`, `latency_ms`, `tokens_used`, `cost_usd` and
`guardrail_status` in `chat_turns.turn_metadata` (see the orchestrator), so the dashboards
below are real aggregates, not canned numbers. Values that are not recorded per turn
(e.g. judge scores) are deliberately not reported here; they live in Langfuse.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession, ChatTurn
from app.models.user import User

# Newest turns first; bounds the work done per request.
MAX_TURNS_SCANNED = 20_000


def _num(meta: Dict[str, Any], key: str) -> float:
    value = (meta or {}).get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


async def _load_turns(db: AsyncSession) -> List[tuple]:
    stmt = (
        select(ChatTurn, ChatSession, User)
        .join(ChatSession, ChatTurn.session_id == ChatSession.id)
        .join(User, ChatSession.user_id == User.id, isouter=True)
        .order_by(ChatTurn.created_at.desc())
        .limit(MAX_TURNS_SCANNED)
    )
    return list((await db.execute(stmt)).all())


class _Totals:
    def __init__(self) -> None:
        self.queries = 0
        self.answers = 0
        self.tokens = 0
        self.cost = 0.0
        self.latency_ms = 0.0
        self.blocked = 0
        self.agents: Counter = Counter()
        self.last_active: Optional[datetime] = None
        self.first_seen: Optional[datetime] = None

    def add(self, turn: ChatTurn) -> None:
        stamp = turn.created_at
        if stamp is not None:
            self.last_active = max(self.last_active, stamp) if self.last_active else stamp
            self.first_seen = min(self.first_seen, stamp) if self.first_seen else stamp
        if turn.role == "user":
            self.queries += 1
            return
        if turn.role != "assistant":
            return
        meta = turn.turn_metadata or {}
        self.answers += 1
        self.tokens += int(_num(meta, "tokens_used"))
        self.cost += _num(meta, "cost_usd")
        self.latency_ms += _num(meta, "latency_ms")
        if str(meta.get("guardrail_status", "PASSED")).upper() != "PASSED":
            self.blocked += 1
        if meta.get("agent_name"):
            self.agents[str(meta["agent_name"])] += 1

    @property
    def avg_latency_ms(self) -> float:
        return round(self.latency_ms / self.answers, 1) if self.answers else 0.0

    @property
    def agents_involved(self) -> List[str]:
        return [name for name, _ in self.agents.most_common()]


async def users_summary(db: AsyncSession) -> List[Dict[str, Any]]:
    rows = await _load_turns(db)
    totals: Dict[str, _Totals] = defaultdict(_Totals)
    profiles: Dict[str, Dict[str, Any]] = {}
    sessions: Dict[str, set] = defaultdict(set)

    for turn, session, user in rows:
        key = (user.email if user else None) or session.user_email or session.user_id or "unknown"
        totals[key].add(turn)
        sessions[key].add(session.id)
        profiles.setdefault(key, {
            "full_name": getattr(user, "full_name", None),
            "department": getattr(user, "department", None),
            "role": getattr(getattr(user, "role", None), "value", None),
        })

    result = []
    for key, t in totals.items():
        profile = profiles[key]
        result.append({
            "user_id": key,
            "email": key if "@" in key else None,
            "full_name": profile["full_name"],
            "department": profile["department"],
            "role": profile["role"],
            "total_sessions": len(sessions[key]),
            "total_queries": t.queries,
            "total_tokens": t.tokens,
            "total_cost_usd": round(t.cost, 6),
            "avg_latency_ms": t.avg_latency_ms,
            "blocked_requests": t.blocked,
            "agents_involved": t.agents_involved,
            "last_active": _iso(t.last_active),
        })
    return sorted(result, key=lambda r: r["total_cost_usd"], reverse=True)


async def sessions_summary(db: AsyncSession, limit: int = 50) -> List[Dict[str, Any]]:
    rows = await _load_turns(db)
    totals: Dict[str, _Totals] = defaultdict(_Totals)
    info: Dict[str, Dict[str, Any]] = {}

    for turn, session, user in rows:
        totals[session.id].add(turn)
        info.setdefault(session.id, {
            "user_id": (user.email if user else None) or session.user_email or session.user_id,
            "user_name": getattr(user, "full_name", None),
            "department": getattr(user, "department", None),
            "title": session.title,
        })

    result = []
    for session_id, t in totals.items():
        result.append({
            "session_id": session_id,
            **info[session_id],
            "turns_count": t.queries + t.answers,
            "total_duration_sec": round(t.latency_ms / 1000.0, 2),
            "total_tokens": t.tokens,
            "total_cost_usd": round(t.cost, 6),
            "blocked_requests": t.blocked,
            "agents_involved": t.agents_involved,
            "created_at": _iso(t.first_seen),
            "last_active": _iso(t.last_active),
        })
    result.sort(key=lambda r: r["last_active"] or "", reverse=True)
    return result[:limit]


async def token_usage_by_department(db: AsyncSession) -> Dict[str, Any]:
    rows = await _load_turns(db)
    totals: Dict[str, _Totals] = defaultdict(_Totals)
    people: Dict[str, set] = defaultdict(set)

    for turn, session, user in rows:
        dept = getattr(user, "department", None) or "Unassigned"
        totals[dept].add(turn)
        people[dept].add((user.id if user else None) or session.user_id or session.id)

    departments = [
        {
            "department": dept,
            "active_employees": len(people[dept]),
            "total_queries": t.queries,
            "total_tokens": t.tokens,
            "estimated_cost_usd": round(t.cost, 6),
            "primary_agents": t.agents_involved[:3],
        }
        for dept, t in sorted(totals.items(), key=lambda kv: kv[1].cost, reverse=True)
    ]
    return {
        "department_metrics": departments,
        "overall_total_tokens": sum(d["total_tokens"] for d in departments),
        "overall_total_cost_usd": round(sum(d["estimated_cost_usd"] for d in departments), 6),
        "turns_scanned": len(rows),
    }

"""The "who is asking" context the HR agents depend on.

The agents' tools take a `user_id`, and the prompts tell the model to address people by first name.
The production pipeline gives the model that information as a header on every message. Anything else
that drives the same agents (ADK Web, ADK evals) must supply the identical text, so it lives here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.core import directory


def build_employee_header(user_id: Optional[str], user_name: Optional[str] = None) -> str:
    resolved_name = user_name or (directory.name_for(user_id) if user_id else None)
    if not resolved_name:
        return f"[Active Employee ID: {user_id}]"
    first_name = resolved_name.split()[0] if " " in resolved_name else resolved_name
    return f"[Active Employee: {resolved_name} (ID: {user_id}) - Address as {first_name}, NEVER call by ID code]"


def build_time_context(now: Optional[datetime] = None) -> str:
    """The "current time" line the pipeline's memory header carries (otherwise the model invents dates)."""
    moment = (now or datetime.now(timezone.utc)).strftime("%A, %B %d, %Y %I:%M %p UTC")
    return f"CURRENT_TIME: {moment}"

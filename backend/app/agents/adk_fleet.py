"""
PeopleOps — Google ADK Autonomous Multi-Agent Fleet
===================================================
Hierarchical Agent Architecture:
hr_root_orchestrator (Agent)
├── leave_agent (Agent)
├── timesheet_agent (Agent)
├── health_agent (Agent)
├── policy_agent (Agent)
└── zoho_agent (Agent)
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from app.core.config import settings
from app.core.llm_bridge import get_llm_model
from app.core.logging_config import AgentLogger
from app.tools.hr_tools import (
    apply_leave,
    calculate_leave_eligibility,
    check_statutory_compliance,
    get_leave_balances,
    get_occupational_health_guidelines,
    get_timesheet_summary,
    log_work_hours,
    query_company_policy,
    sync_zoho_leave_records,
)
from app.services.langfuse_prompt_service import langfuse_prompt_service

logger = logging.getLogger(__name__)
alog = AgentLogger("hr_root_orchestrator")
from app.agents.leave_agent import leave_adk_agent as leave_agent
from app.agents.timesheet_agent import timesheet_adk_agent as timesheet_agent
from app.agents.health_agent import health_adk_agent as health_agent
from app.agents.policy_agent import policy_adk_agent as policy_agent
from app.agents.zoho_agent import zoho_adk_agent as zoho_agent
from app.agents.orchestrator import hr_root_orchestrator


def sync_agent_instructions():
    """Dynamically syncs all agent instructions from Langfuse at runtime."""
    leave_agent.instruction = langfuse_prompt_service.get_prompt("leave-subagent")
    timesheet_agent.instruction = langfuse_prompt_service.get_prompt("timesheet-subagent")
    health_agent.instruction = langfuse_prompt_service.get_prompt("health-subagent")
    policy_agent.instruction = langfuse_prompt_service.get_prompt("policy-rag-subagent")
    zoho_agent.instruction = langfuse_prompt_service.get_prompt("zoho-subagent")
    hr_root_orchestrator.instruction = langfuse_prompt_service.get_prompt("peopleops-root-orchestrator")


# ── Runner Factory & Execution ────────────────────────────────────────────────

def create_hr_runner(session_service: Optional[InMemorySessionService] = None) -> Runner:
    """Create and return an ADK Runner wired to the root HR orchestrator."""
    sync_agent_instructions()
    svc = session_service or InMemorySessionService()
    return Runner(
        agent=hr_root_orchestrator,
        app_name=settings.APP_NAME,
        session_service=svc,
    )


# Global singleton runner
_hr_runner: Optional[Runner] = None


def get_default_hr_runner() -> Runner:
    global _hr_runner
    if _hr_runner is None:
        _hr_runner = create_hr_runner()
    return _hr_runner


async def run_hr_query(
    runner: Runner,
    user_id: str,
    session_id: str,
    message: str,
    context_injection: str = "",
) -> dict:
    """
    Execute a turn through the Google ADK Agent Fleet.

    Returns:
        {
            "response": str,
            "agent_name": str,
            "latency_ms": int,
            "delegation_path": List[str],
        }
    """
    sync_agent_instructions()
    start = time.monotonic()
    alog.agent_start(session_id=session_id, user_id=user_id, message=message)

    # Ensure session exists in ADK SessionService
    existing = runner.session_service.get_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id,
    )
    if existing is None:
        runner.session_service.create_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id,
            state={
                "organization_name": settings.ORGANIZATION_NAME,
                "user_id": user_id,
            }
        )

    full_message = f"[Active Employee ID: {user_id}]\n\n{message}"
    if context_injection:
        full_message = f"[Active Employee ID: {user_id}]\n\n{context_injection}\n\nUSER MESSAGE: {message}"

    content = Content(role="user", parts=[Part(text=full_message)])

    final_response = ""
    final_agent = "hr_root_orchestrator"
    prev_author = None
    delegation_path = ["hr_root_orchestrator"]

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            author = getattr(event, "author", None) or "hr_root_orchestrator"

            if author != prev_author and prev_author is not None:
                alog.agent_delegated(from_agent=prev_author, to_agent=author)
                if author not in delegation_path:
                    delegation_path.append(author)
            prev_author = author

            event_type = type(event).__name__
            detail = ""
            if hasattr(event, "content") and event.content and event.content.parts:
                detail = (event.content.parts[0].text or "")[:100]
            alog.agent_event(event_type=event_type, author=author, details=detail)

            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response = event.content.parts[0].text or ""
                final_agent = author

    except Exception as exc:
        alog.agent_error(error=exc, session_id=session_id)
        logger.error("ADK Agent execution encountered error", exc_info=True)
        final_response = (
            "I apologize, but I encountered an issue processing your request through the HR fleet. "
            "Please try again or contact HR support."
        )

    latency_ms = int((time.monotonic() - start) * 1000)
    alog.agent_done(
        final_agent=final_agent,
        latency_ms=latency_ms,
        response=final_response,
        session_id=session_id,
    )

    return {
        "response": final_response,
        "agent_name": final_agent,
        "latency_ms": latency_ms,
        "delegation_path": delegation_path,
    }

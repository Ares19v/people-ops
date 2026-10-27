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

import inspect
import logging
import time
from typing import Optional

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from app.core.config import settings
from app.core.llm_bridge import (
    GROQ_FALLBACK_MODELS,
    get_active_groq_model,
    get_llm_model,
    resolve_llm_provider,
    switch_groq_fallback_model,
)
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
from app.core.employee_context import build_employee_header

# Patch Google ADK telemetry to prevent 'TypeError: Object of type bytes is not JSON serializable'
try:
    import google.adk.telemetry as _adk_tel
    _orig_trace_call_llm = _adk_tel.trace_call_llm
    def _safe_trace_call_llm(invocation_context, event_id, llm_request, llm_response):
        try:
            _orig_trace_call_llm(invocation_context, event_id, llm_request, llm_response)
        except TypeError as exc:
            # ADK fails to JSON-encode bytes payloads (e.g. inline file parts); tracing must not break the turn.
            logger.debug("Skipped ADK LLM span attributes: %s", exc)
    _adk_tel.trace_call_llm = _safe_trace_call_llm
    import google.adk.flows.llm_flows.base_llm_flow as _base_flow
    _base_flow.trace_call_llm = _safe_trace_call_llm
except Exception:
    logger.debug("Suppressed non-fatal error", exc_info=True)


_root_instruction_override: Optional[str] = None


def set_root_instruction_override(instruction: Optional[str]):
    """Allows experiment benchmarks to evaluate a specific prompt version."""
    global _root_instruction_override
    _root_instruction_override = instruction
    if hr_root_orchestrator:
        if instruction:
            hr_root_orchestrator.instruction = instruction
        else:
            hr_root_orchestrator.instruction = langfuse_prompt_service.get_prompt("peopleops-root-orchestrator", label="live")


def refresh_adk_fleet_models(model_override: Optional[str] = None):
    """Updates the LLM model instance on all ADK agents in the fleet."""
    global _hr_runner
    new_model = get_llm_model(model_override=model_override)
    for agent_obj in (
        hr_root_orchestrator,
        leave_agent,
        timesheet_agent,
        health_agent,
        policy_agent,
        zoho_agent,
    ):
        try:
            agent_obj.model = new_model
        except Exception as exc:
            logger.warning("Failed to update model on agent %s: %s", getattr(agent_obj, "name", "?"), exc)
    # Invalidate cached runner so new queries use the updated model
    _hr_runner = None


def sync_agent_instructions():
    """Dynamically syncs all agent instructions from Langfuse at runtime strictly using the 'live' label unless overridden."""
    leave_agent.instruction = langfuse_prompt_service.get_prompt("leave-subagent", label="live")
    timesheet_agent.instruction = langfuse_prompt_service.get_prompt("timesheet-subagent", label="live")
    health_agent.instruction = langfuse_prompt_service.get_prompt("health-subagent", label="live")
    policy_agent.instruction = langfuse_prompt_service.get_prompt("policy-rag-subagent", label="live")
    zoho_agent.instruction = langfuse_prompt_service.get_prompt("zoho-subagent", label="live")
    if _root_instruction_override:
        hr_root_orchestrator.instruction = _root_instruction_override
    else:
        hr_root_orchestrator.instruction = langfuse_prompt_service.get_prompt("peopleops-root-orchestrator", label="live")


async def _maybe_await(value):
    """ADK session methods are synchronous in 0.x and async from 1.x on; support both."""
    return await value if inspect.isawaitable(value) else value

# ── Runner Factory & Execution ────────────────────────────────────────────────

_ASYNC_DRIVERS = (
    ("postgresql://", "postgresql+asyncpg://"),
    ("postgres://", "postgresql+asyncpg://"),
    ("sqlite://", "sqlite+aiosqlite://"),
)


def _async_session_url(url: str) -> str:
    """ADK 2.x needs an async SQLAlchemy driver; accept the plain URL form people usually have."""
    for plain, asynchronous in _ASYNC_DRIVERS:
        if url.startswith(plain):
            return asynchronous + url[len(plain):]
    return url


def build_session_service():
    """Database-backed ADK sessions when ADK_SESSION_DB_URL is set, otherwise in-memory."""
    if settings.ADK_SESSION_DB_URL:
        try:
            from google.adk.sessions import DatabaseSessionService
            return DatabaseSessionService(db_url=_async_session_url(settings.ADK_SESSION_DB_URL))
        except Exception as exc:
            logger.warning("ADK DatabaseSessionService unavailable (%s); falling back to in-memory sessions", exc)
    return InMemorySessionService()


def create_hr_runner(session_service: Optional[InMemorySessionService] = None) -> Runner:
    """Create and return an ADK Runner wired to the root HR orchestrator."""
    sync_agent_instructions()
    svc = session_service or build_session_service()
    return Runner(
        agent=hr_root_orchestrator,
        app_name=settings.APP_NAME,
        session_service=svc,
    )


# Global singleton runner
_hr_runner: Optional[Runner] = None


def reset_default_hr_runner():
    """Reset cached singleton runner."""
    global _hr_runner
    _hr_runner = None


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
    user_name: Optional[str] = None,
) -> dict:
    """
    Execute a turn through the Google ADK Agent Fleet with automatic model failover.

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

    user_header = build_employee_header(user_id, user_name)

    full_message = f"{user_header}\n\n{message}"
    if context_injection:
        full_message = f"{user_header}\n\n{context_injection}\n\nUSER MESSAGE: {message}"

    content = Content(role="user", parts=[Part(text=full_message)])

    final_response = ""
    final_agent = "hr_root_orchestrator"
    delegation_path = ["hr_root_orchestrator"]

    max_attempts = len(GROQ_FALLBACK_MODELS) if resolve_llm_provider() == "groq" else 1

    for attempt in range(max_attempts):
        # Use a clean per-attempt session id if retrying after a rate limit
        active_session_id = session_id if attempt == 0 else f"{session_id}_retry_{attempt}"
        existing = await _maybe_await(runner.session_service.get_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=active_session_id,
        ))
        if existing is None:
            await _maybe_await(runner.session_service.create_session(
                app_name=runner.app_name,
                user_id=user_id,
                session_id=active_session_id,
                state={
                    "organization_name": settings.ORGANIZATION_NAME,
                    "user_id": user_id,
                }
            ))

        prev_author = None
        delegation_path = ["hr_root_orchestrator"]
        final_response = ""
        final_agent = "hr_root_orchestrator"

        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=active_session_id,
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

            if final_response:
                break

        except Exception as exc:
            alog.agent_error(error=exc, session_id=active_session_id)
            if resolve_llm_provider() == "groq" and attempt + 1 < max_attempts:
                failed_model = get_active_groq_model()
                next_model = switch_groq_fallback_model(failed_model)
                refresh_adk_fleet_models(next_model)
                logger.warning(
                    "ADK Fleet encountered error on '%s' (%s); retrying with fallback model '%s' (attempt %d/%d)",
                    failed_model, exc, next_model, attempt + 2, max_attempts
                )
                continue
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

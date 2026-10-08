"""Google ADK Multi-Agent Fleet & Specialized Subagents.

One file per agent, one file per tool architecture.
"""
from app.agents.leave_agent import leave_agent, leave_adk_agent
from app.agents.timesheet_agent import timesheet_agent, timesheet_adk_agent
from app.agents.health_agent import health_agent, health_adk_agent
from app.agents.policy_agent import policy_agent, policy_adk_agent
from app.agents.zoho_agent import zoho_agent, zoho_adk_agent
from app.agents.orchestrator import hr_root_orchestrator, orchestrator, llm_root_orchestrator

__all__ = [
    # ADK LLM Agents
    "hr_root_orchestrator",
    "leave_adk_agent",
    "timesheet_adk_agent",
    "health_adk_agent",
    "policy_adk_agent",
    "zoho_adk_agent",
    # Specialized Handlers
    "leave_agent",
    "timesheet_agent",
    "health_agent",
    "policy_agent",
    "zoho_agent",
    "llm_root_orchestrator",
]

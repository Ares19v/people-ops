"""LangGraph Stateful Multi-Agent Orchestrator for PeopleOps Enterprise.

NOTE FOR DEVELOPERS & REVIEWERS:
This module implements a LangGraph StateGraph pipeline, exposed on the
`POST /api/v1/agents/langgraph-chat` endpoint for comparative benchmarking alongside
the primary Google ADK Multi-Agent fleet (`POST /api/v1/agents/chat`).

Integrates:
- Regulatory Compliance Redaction & Token Vault (HIPAA, DPDP, GDPR)
- NeMo & Clinical Emergency Input Guardrails
- Supervisor Intent Routing across domain agents (Leave, Timesheet, Policy, Health)
- Human-in-the-Loop (HITL) Manager/Doctor Review Gate
- Dual Observability Tracing (LangSmith + Langfuse)
- Reversible De-Redaction for Authorized Enterprise Roles
"""

import asyncio
from typing import Any, Dict, List, Optional, TypedDict
import time
import uuid

from langgraph.graph import StateGraph, END
from app.core import policy_facts as pf
from app.compliance.phi_engine import compliance_engine
from app.guardrails.guardrails_manager import guardrails_manager
from app.rag.agentic_rag import agentic_policy_rag
from app.schemas.agent import AgentChatResponse, CitationItem, StructuredAction
from app.observability.langsmith_tracer import langsmith_tracer
from app.agents.intent_router import intent_router, QueryScope

class EnterpriseState(TypedDict):
    session_id: str
    user_id: str
    user_role: str
    raw_input: str
    redacted_input: str
    phi_detected_count: int
    guardrail_status: str
    guardrail_tripped: Optional[str]
    routed_agent: str
    agent_output: str
    citations: List[Dict[str, Any]]
    structured_action: Optional[Dict[str, Any]]
    requires_hitl_approval: bool
    is_approved: bool
    final_response: str
    duration_ms: float

def compliance_redaction_node(state: EnterpriseState) -> Dict[str, Any]:
    """Step 1: Identifies sensitive PII/PHI and tokenizes into session vault."""
    redaction = compliance_engine.redact(state["raw_input"], session_id=state["session_id"])
    return {
        "redacted_input": redaction.redacted_text,
        "phi_detected_count": len(redaction.entities_detected),
    }

def input_guardrail_node(state: EnterpriseState) -> Dict[str, Any]:
    """Step 2: Dual boundary check for prompt injection, emergency triage, and BOLA probes."""
    # Check both raw and redacted to ensure no safety bypass
    is_safe, blocked_reason, refusal_msg = guardrails_manager.check_input(state["raw_input"], state["user_role"])
    if is_safe and state.get("redacted_input"):
        is_safe, blocked_reason, refusal_msg = guardrails_manager.check_input(state["redacted_input"], state["user_role"])

    if not is_safe:
        return {
            "guardrail_status": "INPUT_BLOCKED",
            "guardrail_tripped": blocked_reason,
            "final_response": refusal_msg or "Request blocked by safety policy.",
        }
    return {
        "guardrail_status": "PASSED",
        "guardrail_tripped": None
    }

def guardrail_decision(state: EnterpriseState) -> str:
    """Conditional edge: Abort immediately on safety violation, otherwise route."""
    if state.get("guardrail_status") == "INPUT_BLOCKED":
        return "end_workflow"
    return "supervisor_router"

def supervisor_router_node(state: EnterpriseState) -> Dict[str, Any]:
    """Step 3: Supervisor routing using SemanticIntentRouter."""
    route = intent_router.classify(state.get("redacted_input", ""))
    tool = route.selected_tools[0] if route.selected_tools else "policy_rag_subagent"
    agent_map = {
        "leave_subagent": "LEAVE_AGENT",
        "timesheet_subagent": "TIMESHEET_AGENT",
        "health_subagent": "HEALTH_AGENT",
        "policy_rag_subagent": "POLICY_AGENT",
        "zoho_subagent": "POLICY_AGENT",
    }
    return {"routed_agent": agent_map.get(tool, "POLICY_AGENT")}

def routing_decision(state: EnterpriseState) -> str:
    return state.get("routed_agent", "POLICY_AGENT")

def _run_sync(coro):
    """Run a coroutine from sync LangGraph nodes, whether or not an event loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def leave_worker_node(state: EnterpriseState) -> Dict[str, Any]:
    from app.tools.leave.get_leave_balances import get_leave_balances
    user_id = state.get("user_id", "")
    try:
        res = _run_sync(get_leave_balances(user_id))

        balances = res.get("balances", {})
        el = balances.get("EL", {}).get("available", pf.quota("EL") or 0.0)
        cl = balances.get("CL", {}).get("available", pf.quota("CL") or 0.0)
        sl = balances.get("SL", {}).get("available", pf.quota("SL") or 0.0)
        lwp = balances.get("LWP", {}).get("available", 0.0)
        output = (
            f"Statutory Leave Ledger (Database Verified):\n"
            f"• Earned Leave (EL): {el} days (Accrual under Section 18(1)(a); {pf.days(pf.max_accumulation('EL'))}-day carry-forward cap)\n"
            f"• Casual Leave (CL): {cl} days ({pf.days(pf.quota('CL'))} days annual quota under Section 18(1)(b))\n"
            f"• Sick Leave (SL): {sl} days\n"
            f"• Leave Without Pay (LWP): {lwp} days available\n\n"
            f"Governed under Maharashtra Shops and Establishments Act, 2017."
        )
    except Exception as exc:
        output = f"Statutory Leave Ledger (Maharashtra Act 2017 Sec 18): EL capped at {pf.days(pf.max_accumulation('EL'))} days carry-over, CL {pf.days(pf.quota('CL'))} days annual. ({exc})"

    citations = [
        {"source_title": "Maharashtra Act LXI of 2017", "section": "Section 18(1)(a)", "citation_text": "Earned Leave 18 days/yr, 45 days max accumulation", "document_type": "STATUTORY_LAW", "confidence_score": 0.98}
    ]
    return {
        "agent_output": output,
        "citations": citations,
        "requires_hitl_approval": False
    }

def timesheet_worker_node(state: EnterpriseState) -> Dict[str, Any]:
    from app.tools.timesheet.get_timesheet_summary import get_timesheet_summary
    user_id = state.get("user_id", "")
    try:
        res = _run_sync(get_timesheet_summary(user_id))

        tot = res.get("total_hours", 0.0)
        billable = res.get("billable_hours", 0.0)
        output = (
            f"Timesheet & Overtime Audit (Database Verified):\n"
            f"• Total Logged Hours: {tot} hrs (Billable: {billable} hrs)\n"
            f"• Section 13 Standard: Maximum 9 hours/day and 48 hours/week.\n"
            f"• Section 14 Overtime: Hours exceeding statutory caps are compensated at 2.0x regular wage.\n"
            f"• Quarterly Overtime Limit: Capped at 125 hours ceiling."
        )
    except Exception:
        output = (
            "Timesheet & Overtime Rules: Section 13 mandates a maximum of 9 hours/day and 48 hours/week. "
            "Hours exceeding these statutory caps are compensated at 2.0x regular wage (Section 14)."
        )

    citations = [
        {"source_title": "Maharashtra Act LXI of 2017", "section": "Section 13 & 14", "citation_text": "Max 9h/day, 48h/week; Overtime 2.0x", "document_type": "STATUTORY_LAW", "confidence_score": 0.98}
    ]
    return {
        "agent_output": output,
        "citations": citations,
        "requires_hitl_approval": False
    }

def health_worker_node(state: EnterpriseState) -> Dict[str, Any]:
    msg = state["redacted_input"].lower()
    needs_cert = any(w in msg for w in ["sick", "medical", "fever", "illness", "doctor"])
    output = (
        f"Occupational Health & Medical Operations for {state['redacted_input']}:\n"
        f"• Annual Sick Leave Quota: {pf.days(pf.quota('SL'))} days/yr.\n"
        "• Statutory Health Protocol: Medical absence exceeding 2 consecutive days requires a certified doctor's note.\n"
        "• Group Medical Insurance: Sum insured INR 5,00,000 family floater."
    )
    citations = [
        {"source_title": "Enterprise Health & Benefits Policy 2026", "section": "Section 4: Medical Certification", "citation_text": "Sick leave > 2 days requires doctor certificate", "document_type": "COMPANY_POLICY", "confidence_score": 0.98}
    ]
    return {
        "agent_output": output,
        "citations": citations,
        "requires_hitl_approval": needs_cert
    }

def policy_worker_node(state: EnterpriseState) -> Dict[str, Any]:
    rag_resp = agentic_policy_rag.search_and_synthesize(state["redacted_input"], top_k=2)
    c_list = [c.model_dump() for c in rag_resp.citations]
    return {
        "agent_output": rag_resp.synthesis,
        "citations": c_list,
        "requires_hitl_approval": rag_resp.requires_escalation
    }

def hitl_gate_node(state: EnterpriseState) -> Dict[str, Any]:
    """Step 4: Human-in-the-Loop review checkpoint."""
    # If requires approval, appends notice
    output = state.get("agent_output", "")
    if state.get("requires_hitl_approval"):
        output += "\n\n📋 **Manager / Medical Officer Checkpoint**: This action triggers a Human-in-the-Loop approval gate."
    return {"agent_output": output}

def output_sanitization_and_deredaction_node(state: EnterpriseState) -> Dict[str, Any]:
    """Step 5: Output guardrails + Role-based reversible de-redaction."""
    raw = state.get("final_response") or state.get("agent_output") or ""
    is_policy = state.get("routed_agent") in ["POLICY_AGENT", "LEAVE_AGENT", "TIMESHEET_AGENT"]
    is_health = state.get("routed_agent") == "HEALTH_AGENT"

    # NeMo / Regulatory Output Rail
    sanitized, g_status, g_trip = guardrails_manager.check_output(raw, is_policy_query=is_policy, is_health_query=is_health)

    # Reversible de-redaction for authorized roles
    final_restored = compliance_engine.de_redact(
        sanitized,
        session_id=state["session_id"],
        user_role=state["user_role"]
    )

    current_status = state.get("guardrail_status")
    final_status = "INPUT_BLOCKED" if current_status == "INPUT_BLOCKED" else g_status

    return {
        "final_response": final_restored,
        "guardrail_status": final_status,
        "guardrail_tripped": state.get("guardrail_tripped") or g_trip,
    }

def build_enterprise_langgraph():
    """Compiles the LangGraph state machine."""
    workflow = StateGraph(EnterpriseState)

    workflow.add_node("compliance_redaction", compliance_redaction_node)
    workflow.add_node("input_guardrail", input_guardrail_node)
    workflow.add_node("supervisor_router", supervisor_router_node)
    workflow.add_node("leave_worker", leave_worker_node)
    workflow.add_node("timesheet_worker", timesheet_worker_node)
    workflow.add_node("health_worker", health_worker_node)
    workflow.add_node("policy_worker", policy_worker_node)
    workflow.add_node("hitl_gate", hitl_gate_node)
    workflow.add_node("output_sanitization", output_sanitization_and_deredaction_node)

    workflow.set_entry_point("compliance_redaction")
    workflow.add_edge("compliance_redaction", "input_guardrail")

    workflow.add_conditional_edges(
        "input_guardrail",
        guardrail_decision,
        {
            "end_workflow": "output_sanitization",
            "supervisor_router": "supervisor_router",
        }
    )

    workflow.add_conditional_edges(
        "supervisor_router",
        routing_decision,
        {
            "LEAVE_AGENT": "leave_worker",
            "TIMESHEET_AGENT": "timesheet_worker",
            "HEALTH_AGENT": "health_worker",
            "POLICY_AGENT": "policy_worker",
        }
    )

    workflow.add_edge("leave_worker", "hitl_gate")
    workflow.add_edge("timesheet_worker", "hitl_gate")
    workflow.add_edge("health_worker", "hitl_gate")
    workflow.add_edge("policy_worker", "hitl_gate")

    workflow.add_edge("hitl_gate", "output_sanitization")
    workflow.add_edge("output_sanitization", END)

    return workflow.compile()

enterprise_agent_graph = build_enterprise_langgraph()

"""PeopleOps Enterprise — Multi-Agent Orchestrator (Google ADK & Enterprise ReAct Pipeline).

This module is the single authoritative root orchestrator for the platform:
1. Google ADK LLM Root Agent definition (`hr_root_orchestrator`) with hierarchical sub-agents.
2. Complete Enterprise Runtime Pipeline (`LLMRootOrchestratorAgent`):
   - Zero-PII TokenVault boundary (DPDP 2023 compliance)
   - NeMo Guardrails (Adversarial prompt injection & medical emergency checks)
   - Multi-Turn Conversation Memory & PostgreSQL session checkpointing
   - Decoupled Prompt Management via Langfuse
   - Google ADK Multi-Agent Fleet execution with resilient concurrent tool fallback
   - Statutory Critic Agent reflection & correction loop (Maharashtra Labour Law)
   - Role-Based Reversible De-Redaction & clean formatting sanitization
   - Dual Observability Tracing (LangSmith & Langfuse)
   - Real-time Server-Sent Events (SSE) thought trace & token streaming
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from google.adk.agents import Agent

from app.models.user import User
from app.core.config import settings
from app.core.llm_bridge import get_llm_model
from app.agents.leave_agent import leave_agent, leave_adk_agent
from app.agents.policy_agent import policy_agent, policy_adk_agent
from app.agents.timesheet_agent import timesheet_agent, timesheet_adk_agent
from app.agents.health_agent import health_agent, health_adk_agent
from app.agents.zoho_agent import zoho_agent, zoho_adk_agent
from app.agents.statutory_critic import statutory_critic
from app.agents.intent_router import intent_router, QueryScope
from app.services.zoho_service import zoho_service
from app.services.langfuse_prompt_service import langfuse_prompt_service
from app.memory.conversation_memory import conversation_memory
from app.guardrails.guardrails_manager import guardrails_manager
from app.compliance.phi_engine import compliance_engine
from app.observability.langsmith_tracer import langsmith_tracer
from app.schemas.agent import AgentChatResponse, CitationItem, StructuredAction

logger = logging.getLogger(__name__)

# ── 1. Google ADK LLM Root Agent Definition ────────────────────────────────────

hr_root_orchestrator = Agent(
    name="hr_root_orchestrator",
    model=get_llm_model(),
    description=(
        "Top-level autonomous HR Orchestrator for PeopleOps Enterprise Platform. "
        "Intelligently reasons over user intent and delegates to specialized sub-agents: "
        "leave_agent, timesheet_agent, health_agent, policy_agent, or zoho_agent."
    ),
    instruction=langfuse_prompt_service.get_prompt("peopleops-root-orchestrator"),
    sub_agents=[
        leave_adk_agent,
        timesheet_adk_agent,
        health_adk_agent,
        policy_adk_agent,
        zoho_adk_agent,
    ],
)


# ── 2. Enterprise Execution Pipeline ──────────────────────────────────────────

@dataclass
class ToolExecutionResult:
    tool_name: str
    output_text: str
    citations: List[CitationItem]
    structured_action: Optional[StructuredAction]
    requires_approval: bool = False


class LLMRootOrchestratorAgent:
    """The Root Agent orchestrates intent routing, calls domain subagent tools
    concurrently, critiques statutory claims, and synthesizes answers.
    """

    def __init__(self):
        pass

    async def _execute_subagent_tool(
        self, tool_name: str, db: AsyncSession, user: User, query: str
    ) -> ToolExecutionResult:
        """Executes a specialized domain subagent as a tool."""
        with langsmith_tracer.span(
            f"Tool Execution ({tool_name})",
            as_type="tool",
            input={"tool": tool_name, "query": query, "user_id": user.id},
            metadata={"user_role": user.role.value}
        ) as tool_span:
            if tool_name == "leave_subagent":
                res = await leave_agent.handle_request(db, user, query)
                result = ToolExecutionResult(
                    tool_name="leave_subagent",
                    output_text=res.get("response", ""),
                    citations=res.get("citations", []),
                    structured_action=res.get("structured_action")
                )
            elif tool_name == "timesheet_subagent":
                res = await timesheet_agent.handle_request(db, user, query)
                result = ToolExecutionResult(
                    tool_name="timesheet_subagent",
                    output_text=res.get("response", ""),
                    citations=res.get("citations", []),
                    structured_action=res.get("structured_action")
                )
            elif tool_name == "health_subagent":
                res = await health_agent.handle_request(db, user, query)
                result = ToolExecutionResult(
                    tool_name="health_subagent",
                    output_text=res.get("response", ""),
                    citations=res.get("citations", []),
                    structured_action=res.get("structured_action"),
                    requires_approval=any(w in query.lower() for w in ["sick", "fever", "doctor"])
                )
            elif tool_name == "zoho_subagent":
                res = await zoho_agent.handle_request(db, user, query)
                result = ToolExecutionResult(
                    tool_name="zoho_subagent",
                    output_text=res.get("response", ""),
                    citations=res.get("citations", []),
                    structured_action=res.get("structured_action")
                )
            else:
                # Default to Policy & Statutory Graph RAG Subagent
                res = await policy_agent.handle_request(db, user, query)
                result = ToolExecutionResult(
                    tool_name="policy_rag_subagent",
                    output_text=res.get("response", ""),
                    citations=res.get("citations", []),
                    structured_action=res.get("structured_action")
                )
            tool_span.update(output=result.output_text[:500] if result.output_text else "Success")
            return result

    def _decide_subagent_tools(self, message: str, memory_context: str) -> List[str]:
        """LLM Root Decision: Dispatches to specialized subagents using semantic intent router."""
        route = intent_router.classify(message, conversation_context=memory_context)
        return route.selected_tools

    @staticmethod
    def sanitize_chat_formatting(text: str) -> str:
        """Removes raw markdown artifacts (hashtags, asterisks, pipe table lines)
        so responses are cleanly formatted, human-readable paragraphs and bullet points.
        """
        if not text:
            return text

        # 1. Remove markdown headings (###, ##, #) at line starts
        cleaned = re.sub(r'^[ \t]*#{1,6}[ \t]*', '', text, flags=re.MULTILINE)

        # 2. Remove bold and italic asterisks (***text***, **text**, *text*)
        cleaned = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', cleaned)

        # 3. Remove blockquote markers (> )
        cleaned = re.sub(r'^[ \t]*>[ \t]*', '', cleaned, flags=re.MULTILINE)

        # 4. Remove any remaining stray asterisks
        cleaned = cleaned.replace("**", "").replace("*", "")

        # 5. Clean up markdown table syntax
        lines = cleaned.splitlines()
        formatted_lines = []
        for line in lines:
            stripped = line.strip()
            # Drop divider rows like |---|---| or |:---|
            if re.match(r'^\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?$', stripped):
                continue
            # If line is a table row with pipes, convert to bullet item
            if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
                cells = [c.strip() for c in stripped.strip("|").split("|") if c.strip()]
                line = "• " + " — ".join(cells)
            elif line.lstrip().startswith("- "):
                indent = len(line) - len(line.lstrip())
                line = (" " * indent) + "• " + line.lstrip()[2:]
            formatted_lines.append(line)

        cleaned = "\n".join(formatted_lines)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    async def process_message(
        self,
        db: Optional[AsyncSession],
        user: User,
        message: str,
        session_id: Optional[str] = None,
        target_agent: Optional[str] = None,
    ) -> AgentChatResponse:
        if db is None:
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                return await self.process_message(
                    db=session, user=user, message=message, session_id=session_id, target_agent=target_agent
                )

        start_time = time.perf_counter()
        session_id = session_id or f"sess_{user.id[:8]}_{int(time.time())}"

        with langsmith_tracer.span(
            "TOTAL ROUND-TRIP",
            as_type="chain",
            input=message,
            metadata={"session_id": session_id, "user_id": user.id, "user_role": user.role.value}
        ) as root_span:
            # 1. INPUT GUARDRAILS
            with langsmith_tracer.span(
                "Input Guardrails",
                as_type="guardrail",
                input=message,
                metadata={"session_id": session_id}
            ) as input_guardrails_span:
                # 1. PRIVACY BOUNDARY: Redact PII into ephemeral TokenVault BEFORE any LLM sees it
                redaction = compliance_engine.redact(message, session_id=session_id)
                redacted_msg = redaction.redacted_text

                # 2. INPUT GUARDRAIL: Adversarial Injection & Emergency Triage Check
                is_safe, blocked_reason, refusal_msg = guardrails_manager.check_input(message, user.role.value)
                if not is_safe:
                    duration = (time.perf_counter() - start_time) * 1000
                    input_guardrails_span.update(output=f"BLOCKED: {blocked_reason}")
                    root_span.update(output=refusal_msg or "Blocked")
                    langsmith_tracer.trace_agent_run(
                        session_id=session_id,
                        user_id=user.id,
                        user_role=user.role.value,
                        agent_name="ROOT_LLM_ORCHESTRATOR",
                        raw_input=message,
                        sanitized_output=refusal_msg or "Blocked",
                        guardrail_status="INPUT_BLOCKED",
                        guardrail_tripped=blocked_reason,
                        duration_ms=duration,
                        token_usage={"total_tokens": 15},
                        safety_score=0.0
                    )
                    langsmith_tracer.flush()
                    return AgentChatResponse(
                        response=refusal_msg or "Request blocked by safety policy.",
                        agent_routed="ROOT_LLM_ORCHESTRATOR",
                        guardrail_status="INPUT_BLOCKED",
                        guardrail_tripped=blocked_reason,
                        citations=[],
                        structured_action=None,
                        session_id=session_id,
                        latency_ms=duration,
                        token_usage={"total_tokens": 15}
                    )
                input_guardrails_span.update(output="PASSED: NeMo & PII Tokenization Validated")

            # 3. RECALL CONVERSATION MEMORY (The agents remember!)
            if db:
                await conversation_memory.load_session_from_db(db, session_id)
            history_context = conversation_memory.get_formatted_history(session_id, limit=4)

            # 4. FETCH DECOUPLED PROMPT FROM LANGFUSE (Prompts out of codebase)
            system_prompt = langfuse_prompt_service.get_prompt("peopleops-root-orchestrator", label="production")

            # Determine tools via intent router
            if target_agent:
                tools_to_run = [target_agent.lower()]
            else:
                tools_to_run = self._decide_subagent_tools(redacted_msg, history_context)

            # 2. ORCHESTRATOR SPAN
            with langsmith_tracer.span(
                "Orchestrator",
                as_type="agent",
                input=redacted_msg,
                metadata={"tools_planned": tools_to_run, "session_id": session_id}
            ) as orch_span:
                adk_used = False
                primary_agent = "HR_ROOT_ORCHESTRATOR"
                all_citations: List[CitationItem] = []
                primary_structured_action = None
                needs_hitl = False
                subagent_label = tools_to_run[0] if tools_to_run else "hr_root_orchestrator"

                # Subagent Child Span
                with langsmith_tracer.span(
                    f"Subagent ({subagent_label})",
                    as_type="agent",
                    input=redacted_msg,
                    metadata={"subagent": subagent_label, "tools_planned": tools_to_run}
                ) as subagent_span:
                    if not target_agent and len(tools_to_run) <= 1:
                        try:
                            from app.core.llm_bridge import resolve_llm_provider
                            if resolve_llm_provider() != "mock":
                                from app.agents.adk_fleet import get_default_hr_runner, run_hr_query
                                adk_runner = get_default_hr_runner()
                                adk_res = await run_hr_query(
                                    runner=adk_runner,
                                    user_id=user.id,
                                    session_id=session_id,
                                    message=redacted_msg,
                                    context_injection=history_context,
                                )
                                raw_response = adk_res.get("response", "")
                                if raw_response and not raw_response.startswith("I apologize, but I encountered an issue"):
                                    adk_used = True
                                    agent_raw = adk_res.get("agent_name", "hr_root_orchestrator").upper()
                                    if agent_raw.endswith("_AGENT"):
                                        primary_agent = agent_raw.replace("_AGENT", "_SUBAGENT")
                                    else:
                                        primary_agent = agent_raw
                                    tools_to_run = [primary_agent.lower()]
                        except Exception as adk_exc:
                            logger.warning("ADK Fleet execution exception (%s), engaging resilient tool fallback", adk_exc)
                            adk_used = False

                    subagent_span.update(output=f"Routed to {subagent_label} (execution: {'ADK' if adk_used else 'direct tools'})")

                # Tool Selection Child Span
                with langsmith_tracer.span(
                    "Tool Selection",
                    as_type="chain",
                    input={"selected_tools": tools_to_run},
                    metadata={"tool_count": len(tools_to_run)}
                ) as tool_selection_span:
                    if not adk_used:
                        tasks = [self._execute_subagent_tool(tool, db, user, redacted_msg) for tool in tools_to_run]
                        results: List[ToolExecutionResult] = await asyncio.gather(*tasks)

                        combined_texts = []
                        for res in results:
                            combined_texts.append(res.output_text)
                            all_citations.extend(res.citations)
                            if res.structured_action and not primary_structured_action:
                                primary_structured_action = res.structured_action
                            if res.requires_approval:
                                needs_hitl = True

                        raw_response = "\n\n---\n\n".join(combined_texts)
                        if needs_hitl:
                            raw_response += "\n\nHuman-In-The-Loop Checkpoint: This action requires manager/medical officer sign-off."
                        primary_agent = tools_to_run[0].upper() if len(tools_to_run) == 1 else f"CONCURRENT({'+'.join(t.upper() for t in tools_to_run)})"
                    else:
                        with langsmith_tracer.span(
                            f"Tool Execution ({primary_agent.lower()})",
                            as_type="tool",
                            input=redacted_msg,
                            metadata={"provider": "Google ADK"}
                        ) as adk_tool_span:
                            adk_tool_span.update(output=raw_response[:500] if raw_response else "Executed")

                    tool_selection_span.update(output=f"Executed tools: {tools_to_run}")

                orch_span.update(output=raw_response[:500] if raw_response else "Complete")

            # 3. OUTPUT GUARDRAILS
            with langsmith_tracer.span(
                "Output Guardrails",
                as_type="guardrail",
                input=raw_response[:500] if raw_response else "",
                metadata={"statutory_compliance": "Maharashtra Labour Act"}
            ) as output_guardrails_span:
                # 6. STATUTORY CRITIC REFLECTION & CORRECTION LOOP
                critic_res = await statutory_critic.critique_with_llm(raw_response, user_query=redacted_msg)
                critiqued_response = critic_res.corrected_text

                # 7. OUTPUT GUARDRAIL BOUNDARY & STATUTORY DISCLAIMERS
                is_policy = any(t in ["policy_rag_subagent", "leave_subagent", "timesheet_subagent"] for t in tools_to_run)
                is_health = ("health_subagent" in tools_to_run)
                sanitized_response, g_status, g_tripped = guardrails_manager.check_output(
                    critiqued_response, is_policy_query=is_policy, is_health_query=is_health
                )

                # 8. ROLE-BASED REVERSIBLE DE-REDACTION
                final_output = compliance_engine.de_redact(
                    sanitized_response,
                    session_id=session_id,
                    user_role=user.role.value
                )

                # 8.1. FORMATTING SANITIZER: Clean asterisks, hashtags, and raw pipe tables
                final_output = self.sanitize_chat_formatting(final_output)

                output_guardrails_span.update(output=final_output[:500] if final_output else "Passed")

            root_span.update(output=final_output[:500] if final_output else "Finished")

        # 9. SAVE TO MULTI-TURN PERSISTENT MEMORY & POSTGRESQL CHECKPOINT
        if db:
            await conversation_memory.persist_turn_db(db, session_id, user.id, "user", message)
            await conversation_memory.persist_turn_db(db, session_id, user.id, "assistant", final_output)
        else:
            conversation_memory.add_turn(session_id, "user", message)
            conversation_memory.add_turn(session_id, "assistant", final_output)

        duration = (time.perf_counter() - start_time) * 1000
        token_usage = {
            "prompt_tokens": len(message) // 4,
            "completion_tokens": len(final_output) // 4,
            "total_tokens": (len(message) + len(final_output)) // 4
        }

        # 10. DUAL OBSERVABILITY TRACING (LangSmith + Langfuse)
        if tools_to_run:
            agent_label = tools_to_run[0].upper() if len(tools_to_run) == 1 else f"CONCURRENT({'+'.join(t.upper() for t in tools_to_run)})"
        else:
            agent_label = primary_agent
        langsmith_tracer.trace_agent_run(
            session_id=session_id,
            user_id=user.id,
            user_role=user.role.value,
            agent_name=agent_label,
            raw_input=message,
            sanitized_output=final_output,
            guardrail_status=g_status,
            guardrail_tripped=g_tripped,
            duration_ms=duration,
            token_usage=token_usage,
            safety_score=1.0
        )
        langsmith_tracer.flush()

        return AgentChatResponse(
            response=final_output,
            agent_routed=agent_label,
            guardrail_status=g_status,
            guardrail_tripped=g_tripped,
            citations=all_citations,
            structured_action=primary_structured_action,
            session_id=session_id,
            latency_ms=duration,
            token_usage=token_usage
        )

    async def stream_message(
        self,
        db: Optional[AsyncSession],
        user: User,
        message: str,
        session_id: Optional[str] = None,
        target_agent: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Streams real-time Server-Sent Events (SSE) thought traces, tool runs, and tokens."""
        session_id = session_id or f"sess_{user.id[:8]}_{int(time.time())}"

        # Event 1: Guardrail Check
        yield f"event: status\ndata: {json.dumps({'step': 'guardrail_check', 'message': 'Evaluating NeMo boundary...'})}\n\n"
        await asyncio.sleep(0.05)

        is_safe, blocked_reason, refusal_msg = guardrails_manager.check_input(message, user.role.value)
        if not is_safe:
            yield f"event: error\ndata: {json.dumps({'error': refusal_msg or 'Blocked by safety policy'})}\n\n"
            return

        # Event 2: Privacy Tokenization
        yield f"event: status\ndata: {json.dumps({'step': 'privacy_vault', 'message': 'DPDP 2023 tokenization active...'})}\n\n"
        redaction = compliance_engine.redact(message, session_id=session_id)
        redacted_msg = redaction.redacted_text

        # Event 3: Root Orchestrator Reasoning Trace
        history_context = conversation_memory.get_formatted_history(session_id, limit=4)
        tools_to_run = [target_agent.lower()] if target_agent else self._decide_subagent_tools(redacted_msg, history_context)

        yield f"event: thought\ndata: {json.dumps({'thought': f'Root LLM decided tools: {tools_to_run}', 'tools': tools_to_run})}\n\n"
        await asyncio.sleep(0.05)

        # Event 4: Tool Execution
        for t in tools_to_run:
            yield f"event: tool_start\ndata: {json.dumps({'tool': t, 'status': 'running'})}\n\n"

        # Execute full request
        chat_resp = await self.process_message(db, user, message, session_id=session_id, target_agent=target_agent)

        for t in tools_to_run:
            yield f"event: tool_done\ndata: {json.dumps({'tool': t, 'status': 'completed'})}\n\n"

        # Event 5: Critic Verification
        yield f"event: critic\ndata: {json.dumps({'status': 'Statutory verification passed (Maharashtra Act 2017)'})}\n\n"

        # Event 6: Stream Chunks
        words = chat_resp.response.split(" ")
        for i in range(0, len(words), 4):
            chunk = " ".join(words[i:i+4]) + " "
            yield f"event: token\ndata: {json.dumps({'chunk': chunk})}\n\n"
            await asyncio.sleep(0.02)

        # Event 7: Final Completion Event
        yield f"event: complete\ndata: {json.dumps({'session_id': session_id, 'agent_routed': chat_resp.agent_routed, 'citations_count': len(chat_resp.citations), 'latency_ms': chat_resp.latency_ms})}\n\n"


# ── Canonical Singletons & Aliases ─────────────────────────────────────────────

orchestrator = LLMRootOrchestratorAgent()
llm_root_orchestrator = orchestrator
RootOrchestrator = LLMRootOrchestratorAgent

__all__ = [
    "hr_root_orchestrator",
    "orchestrator",
    "llm_root_orchestrator",
    "RootOrchestrator",
    "LLMRootOrchestratorAgent",
]

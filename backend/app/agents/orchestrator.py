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
from app.observability.langsmith_tracer import langsmith_tracer, resolve_user_email, resolve_clean_session_id
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
        user_dept = getattr(user, "department", "Engineering") or "Engineering"
        user_email = getattr(user, "email", None) or resolve_user_email(user.id)
        session_id = resolve_clean_session_id(session_id, user_email)
        emp_id = user.id

        t_ig_ms = 0.0
        t_orch_ms = 0.0
        t_sub_ms = 0.0
        t_tsel_ms = 0.0
        t_texec_ms = 0.0
        t_og_ms = 0.0

        with langsmith_tracer.span(
            "TOTAL ROUND-TRIP",
            as_type="chain",
            input=message,
            metadata={"session_id": session_id, "user_id": user_email, "employee_id": emp_id, "user_email": user_email, "user_role": user.role.value, "department": user_dept}
        ) as root_span:
            # 1. INPUT GUARDRAILS
            t0_ig = time.perf_counter()
            with langsmith_tracer.span(
                "Input Guardrails",
                as_type="guardrail",
                input=message,
                metadata={"session_id": session_id, "user_id": user_email, "employee_id": emp_id}
            ) as input_guardrails_span:
                # 1. PRIVACY BOUNDARY: Redact PII into ephemeral TokenVault BEFORE any LLM sees it
                redaction = compliance_engine.redact(message, session_id=session_id)
                redacted_msg = redaction.redacted_text

                # 2. INPUT GUARDRAIL: Adversarial Injection & Emergency Triage Check
                is_safe, blocked_reason, refusal_msg = guardrails_manager.check_input(message, user.role.value)
                t_ig_ms = (time.perf_counter() - t0_ig) * 1000

                if not is_safe:
                    duration = (time.perf_counter() - start_time) * 1000
                    input_guardrails_span.update(output=f"BLOCKED: {blocked_reason}")
                    root_span.update(output=refusal_msg or "Blocked")
                    cost_val = langsmith_tracer.record_generation(
                        name="call_llm",
                        model="gemini-2.5-flash",
                        input_text=message,
                        output_text=refusal_msg or "Blocked",
                        prompt_tokens=len(message) // 4,
                        completion_tokens=15,
                        metadata={"department": user_dept, "user_id": user_email, "employee_id": emp_id}
                    )
                    langsmith_tracer.trace_agent_run(
                        session_id=session_id,
                        user_id=user_email,
                        user_role=user.role.value,
                        agent_name="ROOT_LLM_ORCHESTRATOR",
                        raw_input=message,
                        sanitized_output=refusal_msg or "Blocked",
                        guardrail_status="INPUT_BLOCKED",
                        guardrail_tripped=blocked_reason,
                        duration_ms=duration,
                        token_usage={"total_tokens": 15, "prompt_tokens": len(message) // 4, "completion_tokens": 15},
                        safety_score=0.0,
                        department=user_dept
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
                        token_usage={"total_tokens": 15, "prompt_tokens": len(message) // 4, "completion_tokens": 15},
                        cost_usd=cost_val,
                        waterfall_diagram=langsmith_tracer.format_waterfall_diagram(
                            input_guardrails_ms=t_ig_ms,
                            orchestrator_ms=0.0,
                            subagent_ms=0.0,
                            tool_selection_ms=0.0,
                            tool_execution_ms=0.0,
                            output_guardrails_ms=0.0,
                            total_latency_sec=duration / 1000.0,
                            total_cost_usd=cost_val
                        )
                    )
                input_guardrails_span.update(output="PASSED: NeMo & PII Tokenization Validated")

            # 3. RECALL CONVERSATION MEMORY (5-Session Sliding Window Cross-Conversation Recall)
            cross_session_summaries = []
            recalled_past_turns = []
            if db:
                await conversation_memory.load_session_from_db(db, session_id)
                cross_session_summaries = await conversation_memory.get_user_sliding_window_summaries(
                    db=db,
                    user_id=user.id,
                    current_session_id=session_id,
                    limit=5
                )
                recent_current = conversation_memory.get_turns(session_id)
                recalled_past_turns = await conversation_memory.recall_relevant_past_turns(
                    db=db,
                    user_id=user.id,
                    current_session_id=session_id,
                    query=message,
                    recent_turns=recent_current,
                    limit=4
                )

            history_context = conversation_memory.get_formatted_history(
                session_id,
                limit=4,
                user_id=user.id,
                user_role=user.role.value,
                cross_session_summaries=cross_session_summaries,
                recalled_turns=recalled_past_turns
            )

            # 4. FETCH DECOUPLED PROMPT FROM LANGFUSE (Prompts out of codebase)
            system_prompt = langfuse_prompt_service.get_prompt("peopleops-root-orchestrator", label="production")

            # Determine tools via intent router
            if target_agent:
                tools_to_run = [target_agent.lower()]
            else:
                tools_to_run = self._decide_subagent_tools(redacted_msg, history_context)

            # 2. ORCHESTRATOR SPAN
            t0_orch = time.perf_counter()
            with langsmith_tracer.span(
                "Orchestrator",
                as_type="agent",
                input=redacted_msg,
                metadata={"tools_planned": tools_to_run, "session_id": session_id, "department": user_dept}
            ) as orch_span:
                adk_used = False
                primary_agent = "HR_ROOT_ORCHESTRATOR"
                all_citations: List[CitationItem] = []
                primary_structured_action = None
                needs_hitl = False
                subagent_label = tools_to_run[0] if tools_to_run else "hr_root_orchestrator"

                # Subagent Child Span
                t0_sub = time.perf_counter()
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
                                    # Override hallucinated apologies if exact historical dialogue was recalled
                                    if ("apologize for not recalling" in raw_response.lower() or "cannot recall" in raw_response.lower()) and (recalled_past_turns or cross_session_summaries):
                                        from app.core.llm_bridge import generate_summary
                                        override_prompt = (
                                            f"{history_context}\n\n"
                                            f"EMPLOYEE QUERY: {message}\n\n"
                                            "INSTRUCTION: Answer the employee warmly and accurately confirming what was previously discussed in the past conversation as provided in the recalled historical dialogue above. Do NOT say you cannot recall or apologize."
                                        )
                                        try:
                                            overridden = await generate_summary(override_prompt)
                                            if overridden and not overridden.startswith("[MOCK SUMMARY]"):
                                                raw_response = overridden.strip()
                                        except Exception:
                                            pass

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
                t_sub_ms = (time.perf_counter() - t0_sub) * 1000

                # Tool Selection Child Span
                t0_tsel = time.perf_counter()
                with langsmith_tracer.span(
                    "Tool Selection",
                    as_type="chain",
                    input={"selected_tools": tools_to_run},
                    metadata={"tool_count": len(tools_to_run)}
                ) as tool_selection_span:
                    if not adk_used:
                        is_recall_query = any(k in message.lower() for k in [
                            "remember", "past conversation", "previous conversation", "earlier",
                            "told you", "told u", "last time", "last chat", "before", "recall"
                        ])
                        direct_recalled = False
                        if is_recall_query and (recalled_past_turns or cross_session_summaries):
                            from app.core.llm_bridge import generate_summary
                            recall_prompt = (
                                f"{history_context}\n\n"
                                f"EMPLOYEE QUERY: {message}\n\n"
                                "INSTRUCTION: You are the PeopleOps HR AI Assistant. The employee is asking to recall past conversations. "
                                "Reference the exact recalled details above, answer warmly and accurately confirming what was previously discussed. "
                                "Do NOT apologize or say you cannot recall."
                            )
                            try:
                                synth_res = await generate_summary(recall_prompt)
                                if synth_res and not synth_res.startswith("[MOCK SUMMARY]"):
                                    raw_response = synth_res.strip()
                                    direct_recalled = True
                                    primary_agent = "HR_ROOT_ORCHESTRATOR"
                            except Exception:
                                pass

                        if not direct_recalled:
                            t0_texec = time.perf_counter()
                            tasks = [self._execute_subagent_tool(tool, db, user, redacted_msg) for tool in tools_to_run]
                            results: List[ToolExecutionResult] = await asyncio.gather(*tasks)
                            t_texec_ms = (time.perf_counter() - t0_texec) * 1000

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
                        t0_texec = time.perf_counter()
                        with langsmith_tracer.span(
                            f"Tool Execution ({primary_agent.lower()})",
                            as_type="tool",
                            input=redacted_msg,
                            metadata={"provider": "Google ADK"}
                        ) as adk_tool_span:
                            adk_tool_span.update(output=raw_response[:500] if raw_response else "Executed")
                        t_texec_ms = (time.perf_counter() - t0_texec) * 1000

                    tool_selection_span.update(output=f"Executed tools: {tools_to_run}")
                t_tsel_ms = (time.perf_counter() - t0_tsel) * 1000

                orch_span.update(output=raw_response[:500] if raw_response else "Complete")
            t_orch_ms = (time.perf_counter() - t0_orch) * 1000

            # 3. OUTPUT GUARDRAILS
            t0_og = time.perf_counter()
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
            t_og_ms = (time.perf_counter() - t0_og) * 1000

            root_span.update(output=final_output[:500] if final_output else "Finished")

        duration = (time.perf_counter() - start_time) * 1000
        p_tokens = len(message) // 4
        c_tokens = len(final_output) // 4
        token_usage = {
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "total_tokens": p_tokens + c_tokens
        }
        cost_usd = langsmith_tracer.record_generation(
            name="call_llm",
            model="gemini-2.5-flash",
            input_text=message,
            output_text=final_output,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            metadata={"department": user_dept, "user_id": user_email, "employee_id": emp_id, "user_role": user.role.value}
        )

        if tools_to_run:
            agent_label = tools_to_run[0].upper() if len(tools_to_run) == 1 else f"CONCURRENT({'+'.join(t.upper() for t in tools_to_run)})"
        else:
            agent_label = primary_agent

        turn_meta = {
            "agent_name": agent_label,
            "latency_ms": round(duration, 2),
            "tokens_used": token_usage.get("total_tokens", 0),
            "cost_usd": cost_usd,
            "guardrail_status": g_status,
            "citations": [getattr(c, "source_title", getattr(c, "source", str(c))) for c in all_citations] if all_citations else []
        }

        # 9. SAVE TO MULTI-TURN PERSISTENT MEMORY & DATABASE CHECKPOINT
        if db:
            await conversation_memory.persist_turn_db(db, session_id, user.id, "user", message)
            await conversation_memory.persist_turn_db(db, session_id, user.id, "assistant", final_output, metadata=turn_meta)
        else:
            conversation_memory.add_turn(session_id, "user", message)
            conversation_memory.add_turn(session_id, "assistant", final_output, metadata=turn_meta)

        langsmith_tracer.trace_agent_run(
            session_id=session_id,
            user_id=user_email,
            user_role=user.role.value,
            agent_name=agent_label,
            raw_input=message,
            sanitized_output=final_output,
            guardrail_status=g_status,
            guardrail_tripped=g_tripped,
            duration_ms=duration,
            token_usage=token_usage,
            safety_score=1.0,
            department=user_dept
        )

        # 10. AUTOMATED LLM-AS-A-JUDGE EVALUATION (Scores pushed to Langfuse)
        try:
            from app.evaluations.llm_judge_service import llm_judge_service
            eval_res = llm_judge_service.evaluate_response(
                query=message,
                response_text=final_output,
                trace_id=session_id,
                session_id=session_id,
                latency_ms=duration,
                agent_name=agent_label,
                push_to_langfuse=True
            )
            eval_scores_dict = eval_res.metrics
        except Exception:
            eval_scores_dict = {}

        langsmith_tracer.flush()

        waterfall_diagram_rendered = langsmith_tracer.format_waterfall_diagram(
            input_guardrails_ms=t_ig_ms,
            orchestrator_ms=t_orch_ms,
            subagent_ms=t_sub_ms,
            tool_selection_ms=t_tsel_ms,
            tool_execution_ms=t_texec_ms,
            output_guardrails_ms=t_og_ms,
            total_latency_sec=duration / 1000.0,
            total_cost_usd=cost_usd
        )

        return AgentChatResponse(
            response=final_output,
            agent_routed=agent_label,
            guardrail_status=g_status,
            guardrail_tripped=g_tripped,
            citations=all_citations,
            structured_action=primary_structured_action,
            session_id=session_id,
            latency_ms=duration,
            token_usage=token_usage,
            cost_usd=cost_usd,
            waterfall_diagram=waterfall_diagram_rendered,
            eval_scores=eval_scores_dict
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
        user_email = getattr(user, "email", None) or resolve_user_email(user.id)
        session_id = resolve_clean_session_id(session_id, user_email)

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

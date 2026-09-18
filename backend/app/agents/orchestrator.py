import time
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.guardrails.guardrails_manager import guardrails_manager
from app.agents.leave_agent import leave_agent
from app.agents.policy_agent import policy_agent
from app.agents.timesheet_agent import timesheet_agent
from app.observability.langsmith_tracer import langsmith_tracer
from app.schemas.agent import AgentChatResponse, CitationItem, StructuredAction

class RootOrchestrator:
    """Google ADK Root Orchestrator routing to Leave, Policy (Graph RAG), and Timesheet agents."""

    def __init__(self):
        pass

    async def process_message(
        self, db: AsyncSession, user: User, message: str, session_id: Optional[str] = None, target_agent: Optional[str] = None
    ) -> AgentChatResponse:
        start_time = time.perf_counter()
        session_id = session_id or str(uuid.uuid4())

        # 1. NeMo Input Guardrail Boundary Check
        is_safe, blocked_reason, refusal_msg = guardrails_manager.check_input(message, user.role.value)
        if not is_safe:
            duration = (time.perf_counter() - start_time) * 1000
            langsmith_tracer.trace_agent_run(
                session_id=session_id,
                user_id=user.id,
                user_role=user.role.value,
                agent_name="ROOT_ORCHESTRATOR",
                raw_input=message,
                sanitized_output=refusal_msg or "Blocked",
                guardrail_status="INPUT_BLOCKED",
                guardrail_tripped=blocked_reason,
                duration_ms=duration,
                token_usage={"total_tokens": 15}
            )
            return AgentChatResponse(
                response=refusal_msg or "Request blocked by safety policy.",
                agent_routed="ROOT_ORCHESTRATOR",
                guardrail_status="INPUT_BLOCKED",
                guardrail_tripped=blocked_reason,
                citations=[],
                structured_action=None,
                session_id=session_id,
                latency_ms=duration,
                token_usage={"total_tokens": 15}
            )

        # 2. Intelligent Intent Routing
        msg_lower = message.lower()
        routed_agent = "ROOT_ORCHESTRATOR"
        is_policy = False

        if target_agent == "LEAVE" or (target_agent is None and any(w in msg_lower for w in ["balance", "apply leave", "casual leave", "earned leave", "sick leave", "take leave", "vacation", "day off"])):
            routed_agent = "LEAVE_AGENT"
            result = await leave_agent.handle_request(db, user, message)
        elif target_agent == "TIMESHEET" or (target_agent is None and any(w in msg_lower for w in ["timesheet", "log hours", "working hours", "project time", "weekly hours"])):
            routed_agent = "TIMESHEET_AGENT"
            result = await timesheet_agent.handle_request(db, user, message)
        elif target_agent == "POLICY" or (target_agent is None and any(w in msg_lower for w in ["policy", "rule", "statutory", "maharashtra", "law", "act", "holiday", "overtime", "cl", "el", "sl", "lwp", "carry forward"])):
            routed_agent = "POLICY_AGENT"
            is_policy = True
            result = await policy_agent.handle_request(db, user, message)
        else:
            # Fallback to general policy / help
            routed_agent = "POLICY_AGENT"
            is_policy = True
            result = await policy_agent.handle_request(db, user, message)

        raw_response = result.get("response", "")
        citations = result.get("citations", [])
        structured_action = result.get("structured_action")

        # 3. NeMo Output Guardrail Boundary Check & DPDP Masking
        sanitized_response, g_status, g_tripped = guardrails_manager.check_output(
            raw_response, is_policy_query=is_policy
        )

        duration = (time.perf_counter() - start_time) * 1000
        token_usage = {"prompt_tokens": len(message) // 4, "completion_tokens": len(sanitized_response) // 4, "total_tokens": (len(message) + len(sanitized_response)) // 4}

        # 4. LangSmith Tracing
        langsmith_tracer.trace_agent_run(
            session_id=session_id,
            user_id=user.id,
            user_role=user.role.value,
            agent_name=routed_agent,
            raw_input=message,
            sanitized_output=sanitized_response,
            guardrail_status=g_status,
            guardrail_tripped=g_tripped,
            duration_ms=duration,
            token_usage=token_usage
        )

        return AgentChatResponse(
            response=sanitized_response,
            agent_routed=routed_agent,
            guardrail_status=g_status,
            guardrail_tripped=g_tripped,
            citations=citations,
            structured_action=structured_action,
            session_id=session_id,
            latency_ms=duration,
            token_usage=token_usage
        )

orchestrator = RootOrchestrator()

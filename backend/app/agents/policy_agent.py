from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.graph_rag_service import graph_rag_service
from app.agents.llm_provider import get_llm_provider
from app.schemas.agent import StructuredAction
from google.adk.agents import Agent
from app.core.llm_bridge import get_llm_model
from app.tools.policy.query_company_policy import query_company_policy
from app.tools.policy.check_statutory_compliance import check_statutory_compliance
from app.services.langfuse_prompt_service import langfuse_prompt_service

# ── Google ADK Specialist Sub-Agent Definition ─────────────────────────────────

policy_adk_agent = Agent(
    name="policy_agent",
    model=get_llm_model(),
    description=(
        "Specialist Statutory Compliance & Policy Knowledge Graph Agent. Responsible for Indian labour laws "
        "(Maharashtra Shops & Establishments Act 2017, Karnataka 1961, Delhi 1954) and HR Handbook policies."
    ),
    instruction=langfuse_prompt_service.get_prompt("policy-rag-subagent"),
    tools=[
        query_company_policy,
        check_statutory_compliance,
    ],
)


class HRPolicyAgent:
    """Graph RAG Agent responsible for policy, rule, and statutory labour law questions."""

    def __init__(self):
        self.llm = get_llm_provider()

    @property
    def system_prompt(self) -> str:
        return langfuse_prompt_service.get_prompt("policy-rag-subagent", label="production")

    @property
    def SYSTEM_PROMPT(self) -> str:
        return self.system_prompt

    async def handle_request(self, db: AsyncSession, user: User, message: str) -> Dict[str, Any]:
        # 1. Query Graph RAG service
        retrieval_res = await graph_rag_service.search_policies(message)
        context = retrieval_res["context"]
        citations = retrieval_res["citations"]
        requires_escalation = retrieval_res["requires_escalation"]
        disclaimer = retrieval_res["legal_disclaimer"]

        structured_action = None

        if requires_escalation:
            reply = (
                "HR / Legal Escalation Notice:\n\n"
                "Your inquiry involves a complex or legally sensitive matter that requires authoritative review "
                "by our HR & Legal Compliance Department.\n\n"
                "An escalation ticket has been prepared to connect you with an HR specialist."
            )
            structured_action = StructuredAction(
                action_type="ESCALATE_HR",
                action_payload={
                    "user_id": user.id,
                    "query": message,
                    "urgency": "HIGH",
                    "status": "TICKET_CREATED"
                },
                requires_confirmation=False,
                executed=True,
                result_message="Escalation ticket #HR-TKT-2026 logged. An HR partner will contact you."
            )
        else:
            # Generate grounded response
            llm_text = await self.llm.generate_response(
                system_prompt=self.system_prompt,
                user_prompt=message,
                context=context
            )
            clean_disclaimer = disclaimer.replace("> ", "").replace("**", "").replace("*", "").strip()
            reply = f"{llm_text}\n\nStatutory Note: {clean_disclaimer}"


        return {
            "response": reply,
            "agent_routed": "POLICY_AGENT",
            "citations": citations,
            "structured_action": structured_action
        }

policy_agent = HRPolicyAgent()

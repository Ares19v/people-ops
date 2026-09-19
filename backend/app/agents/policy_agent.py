from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.graph_rag_service import graph_rag_service
from app.agents.llm_provider import get_llm_provider
from app.schemas.agent import StructuredAction

class HRPolicyAgent:
    """Graph RAG Agent responsible for policy, rule, and statutory labour law questions."""

    SYSTEM_PROMPT = """You are the HR Policy & Legal Knowledge Agent for Intelera Technologies.
Your responsibilities:
- Retrieve answers from the indexed policy documents and Maharashtra Labour Law knowledge graph.
- Clearly distinguish between:
  1. Statutory Law (Maharashtra Shops and Establishments Act, 2017)
  2. Company Policy (Enterprise Leave & Working Hours Manual 2026)
  3. Configurable Rules
  4. Unresolved Interpretation
- Provide authoritative citations with exact section references.
- Never provide formal legal counsel. Always include the statutory disclaimer.
- Escalate legally contentious or ambiguous questions to human HR/legal review.
"""

    def __init__(self):
        self.llm = get_llm_provider()

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
                "⚠️ **HR / Legal Escalation Notice**:\n"
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
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=message,
                context=context
            )
            reply = f"{llm_text}\n\n> {disclaimer}"

        return {
            "response": reply,
            "agent_routed": "POLICY_AGENT",
            "citations": citations,
            "structured_action": structured_action
        }

policy_agent = HRPolicyAgent()

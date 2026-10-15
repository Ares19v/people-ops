"""Occupational Health and Medical Benefits Agent for PeopleOps Enterprise."""

from typing import Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.rag.agentic_rag import agentic_policy_rag
from app.schemas.agent import CitationItem
from google.adk.agents import Agent
from app.core.llm_bridge import get_llm_model
from app.tools.health.get_occupational_health_guidelines import get_occupational_health_guidelines
from app.tools.leave.get_leave_balances import get_leave_balances
from app.services.langfuse_prompt_service import langfuse_prompt_service

# ── Google ADK Specialist Sub-Agent Definition ─────────────────────────────────

health_adk_agent = Agent(
    name="health_agent",
    model=get_llm_model(),
    description=(
        "Specialist Occupational Health & Medical Triage Agent. Responsible for health guidelines, "
        "medical certificate requirements for prolonged absences, and health leave triage."
    ),
    instruction=langfuse_prompt_service.get_prompt("health-subagent", label="live"),
    tools=[
        get_occupational_health_guidelines,
        get_leave_balances,
    ],
)


class HealthAgent:
    """Specialized worker agent handling Employee Health, Medical Certificates, and Insurance Benefits."""

    @property
    def system_prompt(self) -> str:
        return langfuse_prompt_service.get_prompt("health-subagent", label="live")

    @property
    def SYSTEM_PROMPT(self) -> str:
        return self.system_prompt


    async def handle_request(self, db: AsyncSession, user: User, message: str) -> Dict[str, Any]:
        msg_lower = message.lower()
        rag_resp = agentic_policy_rag.search_and_synthesize(message, top_k=2)

        # Build response
        response_parts = []

        first_name = user.full_name.split()[0] if user.full_name else "there"

        if any(w in msg_lower for w in ["sick leave", "medical leave", "doctor certificate", "medical certificate", "fever", "sick", "unwell"]):
            response_parts.append(
                f"I'm sorry to hear that you're feeling unwell, {first_name}! Please take care of yourself.\n\n"
                "Here are the key sick leave guidelines to keep in mind:\n"
                "• Full-time personnel are entitled to 12 days of paid Sick Leave (SL) per year.\n"
                "• Medical Note Protocol: Absence exceeding 2 consecutive days mandates submission of a signed medical certificate from a registered physician.\n"
                "• Confidentiality: Health records are secured under HIPAA and DPDP standards with zero unredacted PII exposure.\n\n"
                "Rest up and get well soon! Would you like me to help log your absence for today?"
            )
        elif any(w in msg_lower for w in ["insurance", "mediclaim", "coverage", "hospitalization"]):
            response_parts.append(
                "Enterprise Group Health Insurance Plan 2026:\n\n"
                "• Sum Insured: INR 5,00,000 family floater (covers employee, spouse, and up to 2 children).\n"
                "• Pre-existing Diseases: Covered from Day 1 of joining with cashless network access.\n"
                "• Pre/Post Hospitalization: 30 days pre-hospitalization and 60 days post-discharge."
            )
        else:
            response_parts.append(rag_resp.synthesis)

        final_text = "\n\n".join(response_parts)

        # Citations
        citations = rag_resp.citations or [
            CitationItem(
                source_title="Enterprise Occupational Health Policy 2026",
                section="Section 4: Medical Certification & Coverage",
                document_type="COMPANY_POLICY",
                citation_text="Sick leave > 2 days mandates medical certification; Group Mediclaim capped at INR 5,00,000.",
                confidence_score=0.98
            )
        ]

        return {
            "response": final_text,
            "citations": citations,
            "structured_action": None,
            "agent": "HEALTH_AGENT"
        }

health_agent = HealthAgent()

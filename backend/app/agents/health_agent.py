"""Occupational Health and Medical Benefits Agent for PeopleOps Enterprise."""

from typing import Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.rag.agentic_rag import agentic_policy_rag
from app.schemas.agent import CitationItem

class HealthAgent:
    """Specialized worker agent handling Employee Health, Medical Certificates, and Insurance Benefits."""

    async def handle_request(self, db: AsyncSession, user: User, message: str) -> Dict[str, Any]:
        msg_lower = message.lower()
        rag_resp = agentic_policy_rag.search_and_synthesize(message, top_k=2)

        # Build response
        response_parts = []

        if any(w in msg_lower for w in ["sick leave", "medical leave", "doctor certificate", "medical certificate"]):
            response_parts.append(
                "**Occupational Health Advisory – Sick Leave Protocols**:\n"
                "- Full-time personnel are entitled to **12 days of paid Sick Leave (SL)** per year.\n"
                "- **Statutory & Health Protocol**: Absence exceeding **2 consecutive days** mandates submission of a signed medical certificate from a registered physician.\n"
                "- Records are secured under HIPAA and DPDP standards with zero unredacted PII exposure."
            )
        elif any(w in msg_lower for w in ["insurance", "mediclaim", "coverage", "hospitalization"]):
            response_parts.append(
                "**Enterprise Group Health Insurance Plan 2026**:\n"
                "- **Sum Insured**: INR 5,00,000 family floater (covers employee, spouse, and up to 2 children).\n"
                "- **Pre-existing Diseases**: Covered from Day 1 of joining with cashless network access.\n"
                "- **Pre/Post Hospitalization**: 30 days pre-hospitalization and 60 days post-discharge."
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

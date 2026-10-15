"""Zoho People HRMS Integration Agent for PeopleOps Enterprise.

Uses Google ADK Agent class and dedicated Zoho sync tools.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from google.adk.agents import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm_bridge import get_llm_model
from app.models.user import User
from app.schemas.agent import CitationItem
from app.services.langfuse_prompt_service import langfuse_prompt_service
from app.services.zoho_service import zoho_service
from app.tools.zoho.sync_zoho_leave_records import sync_zoho_leave_records

logger = logging.getLogger(__name__)


# ── Google ADK Specialist Sub-Agent Definition ─────────────────────────────────

zoho_adk_agent = Agent(
    name="zoho_agent",
    model=get_llm_model(),
    description=(
        "Specialist Zoho People HRMS Integration Agent. Responsible for querying external "
        "synchronized records from Zoho People REST v2 API."
    ),
    instruction=langfuse_prompt_service.get_prompt("zoho-subagent", label="live"),
    tools=[
        sync_zoho_leave_records,
    ],
)


# ── Handlers & Runtime Compatibility ───────────────────────────────────────────

class ZohoAgent:
    """Specialized worker agent handling Zoho People HRMS live sync."""

    @property
    def system_prompt(self) -> str:
        return langfuse_prompt_service.get_prompt("zoho-subagent", label="live")

    @property
    def SYSTEM_PROMPT(self) -> str:
        return self.system_prompt

    async def handle_request(self, db: AsyncSession, user: User, message: str) -> Dict[str, Any]:
        zoho_records = await zoho_service.get_leave_records(user.id)
        first_name = user.full_name.split()[0] if user.full_name else "there"
        zoho_text = f"Zoho People System Sync:\nHi {first_name}, here is your live synchronized record report:\n\n"
        zoho_text += f"Found {len(zoho_records)} synchronized leave records in Zoho REST API v2:\n\n"
        for r in zoho_records:
            zoho_text += f"• {r.leave_type} ({r.days} days): {r.from_date} to {r.to_date} [{r.status}]\n"

        citations = [
            CitationItem(
                source_title="Zoho People REST API v2",
                section="/leave/getLeaveRecords",
                document_type="COMPANY_POLICY",
                citation_text=f"Live synchronized records for Employee {user.id}",
                confidence_score=0.99,
            )
        ]

        return {
            "response": zoho_text.strip(),
            "agent_routed": "ZOHO_SUBAGENT",
            "citations": citations,
            "structured_action": None,
        }


zoho_agent = ZohoAgent()

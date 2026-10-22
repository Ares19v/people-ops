import re
from datetime import date, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import policy_facts as pf
from app.models.user import User
from app.models.leave import LeaveType
from app.services.leave_service import LeaveService
from app.schemas.agent import StructuredAction
from app.agents.llm_provider import get_llm_provider
from google.adk.agents import Agent
from app.core.llm_bridge import get_llm_model
from app.tools.leave.get_leave_balances import get_leave_balances
from app.tools.leave.calculate_leave_eligibility import calculate_leave_eligibility
from app.tools.leave.apply_leave import apply_leave
from app.services.langfuse_prompt_service import langfuse_prompt_service

# ── Google ADK Specialist Sub-Agent Definition ─────────────────────────────────

leave_adk_agent = Agent(
    name="leave_agent",
    model=get_llm_model(),
    description=(
        "Specialist HR Leave Agent. Responsible for querying available leave balances "
        "(Casual Leave CL, Earned Leave EL, Sick Leave SL, Leave Without Pay LWP), "
        "calculating eligibility, and submitting leave requests."
    ),
    instruction=langfuse_prompt_service.get_prompt("leave-subagent", label="live"),
    tools=[
        get_leave_balances,
        calculate_leave_eligibility,
        apply_leave,
    ],
)


class LeaveAgent:
    """Agent responsible for leave balance querying, leave application assistance, and rule validation."""

    def __init__(self):
        self.llm = get_llm_provider()

    @property
    def system_prompt(self) -> str:
        return langfuse_prompt_service.get_prompt("leave-subagent", label="live")

    @property
    def SYSTEM_PROMPT(self) -> str:
        return self.system_prompt


    async def handle_request(self, db: AsyncSession, user: User, message: str) -> Dict[str, Any]:
        msg_lower = message.lower()
        structured_action: Optional[StructuredAction] = None

        # 1. Fetch real balances deterministically
        balance_summary = await LeaveService.get_balance_summary(db, user.id)
        balance_map = {b.leave_type.value: b.available_balance for b in balance_summary.balances}

        # Check if user is confirming a pending draft (e.g. "Yes, proceed", "submit it")
        confirm_intent = bool(re.search(r"\b(yes|proceed|confirm|submit|go ahead|approve|do it)\b", msg_lower)) and not bool(re.search(r"\b(no|cancel|don't|dont|wait)\b", msg_lower))
        
        # Check if user wants to apply for leave
        apply_intent = bool(re.search(r"\b(apply|take|request|book|need)\b", msg_lower)) and bool(re.search(r"\b(leave|leaves|day off|days off|vacation|pto)\b", msg_lower))
        
        # Detect leave type mentioned
        detected_type = LeaveType.CL
        if "earned" in msg_lower or re.search(r"\bel\b", msg_lower) or "privilege" in msg_lower:
            detected_type = LeaveType.EL
        elif "sick" in msg_lower or re.search(r"\bsl\b", msg_lower) or "medical" in msg_lower:
            detected_type = LeaveType.SL
        elif "without pay" in msg_lower or re.search(r"\blwp\b", msg_lower):
            detected_type = LeaveType.LWP

        type_names = {
            LeaveType.CL: "Casual Leave (CL)",
            LeaveType.EL: "Earned Leave (EL)",
            LeaveType.SL: "Sick Leave (SL)",
            LeaveType.LWP: "Leave Without Pay (LWP)"
        }
        type_display = type_names.get(detected_type, detected_type.value)
        first_name = user.full_name.split()[0] if user.full_name else "there"
        avail = balance_map.get(detected_type.value, 0.0)

        if confirm_intent and not apply_intent:
            # User is confirming the previous draft
            start_d = date.today() + timedelta(days=1)
            end_d = start_d
            reply = (
                f"Your leave application for {type_display} has been successfully submitted and forwarded to your Reporting Manager for formal approval!\n\n"
                f"• Reference ID: LV-{date.today().strftime('%Y%m%d')}-001\n"
                f"• Status: Pending Manager Sign-off\n"
                f"• Available Balance: {avail} days\n\n"
                f"You will receive an automated notification once your manager reviews it."
            )
            structured_action = StructuredAction(
                action_type="LEAVE_APPLY",
                action_payload={
                    "leave_type": detected_type.value,
                    "start_date": str(start_d),
                    "end_date": str(end_d),
                    "status": "SUBMITTED"
                },
                requires_confirmation=False,
                executed=True
            )
        elif apply_intent:
            # Parse dates if specified (e.g. "Oct 20", "October 20th", "Nov 5")
            start_d = date.today() + timedelta(days=1)
            months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
            m_match = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})\b", msg_lower)
            if m_match:
                m_str, d_str = m_match.group(1)[:3], int(m_match.group(2))
                yr = date.today().year
                try:
                    start_d = date(yr, months[m_str], d_str)
                    if start_d < date.today():
                        start_d = date(yr + 1, months[m_str], d_str)
                except Exception:
                    start_d = date.today() + timedelta(days=1)
            
            end_d = start_d
            
            # Check for multi-day mentions like "2 days" or "3 days"
            day_match = re.search(r"(\d+)\s*days?", msg_lower)
            if day_match:
                count = int(day_match.group(1))
                end_d = start_d + timedelta(days=max(0, count - 1))

            req_days = float((end_d - start_d).days + 1)

            if detected_type != LeaveType.LWP and req_days > avail:
                reply = (
                    f"Heads up, {first_name} (Insufficient balance): You've requested {req_days} day(s) of {type_display}, "
                    f"but your available balance is currently {avail} day(s). "
                    f"You can apply for Leave Without Pay (LWP) instead, or adjust your requested dates."
                )
            else:
                reply = (
                    f"I've drafted your leave application for {type_display} from "
                    f"{start_d.strftime('%b %d, %Y')} to {end_d.strftime('%b %d, %Y')} ({req_days} day(s)).\n\n"
                    f"• Current Available Balance: {avail} days\n"
                    f"• Approver: Your designated Reporting Manager\n\n"
                    f"Would you like me to confirm and submit this application?"
                )
                structured_action = StructuredAction(
                    action_type="LEAVE_APPLY",
                    action_payload={
                        "leave_type": detected_type.value,
                        "start_date": str(start_d),
                        "end_date": str(end_d),
                        "reason": f"Applied via AI Assistant: {message[:100]}"
                    },
                    requires_confirmation=True,
                    executed=False
                )
        else:
            first_name = user.full_name.split()[0] if user.full_name else "there"
            # Informational balance reply
            reply = (
                f"Hi {first_name}, here are your verified leave balances:\n\n"
                f"• Earned Leave (EL): {balance_map.get('EL', 0.0)} days (Accrues monthly; max accumulation {pf.days(pf.max_accumulation('EL'))} days)\n"
                f"• Casual Leave (CL): {balance_map.get('CL', 0.0)} days ({pf.days(pf.quota('CL'))} days per year; non-cumulative)\n"
                f"• Sick Leave (SL): {balance_map.get('SL', 0.0)} days (Cumulative up to {pf.days(pf.max_accumulation('SL'))} days)\n"
                f"• Leave Without Pay (LWP): Uncapped (Discretionary management approval)\n\n"
                f"Would you like me to help you prepare a leave application or book upcoming time off?"
            )

        return {
            "response": reply,
            "agent_routed": "LEAVE_AGENT",
            "structured_action": structured_action,
            "citations": []
        }

leave_agent = LeaveAgent()

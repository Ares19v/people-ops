import re
from datetime import date, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

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
    instruction=langfuse_prompt_service.get_prompt("leave-subagent"),
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
        return langfuse_prompt_service.get_prompt("leave-subagent", label="production")

    @property
    def SYSTEM_PROMPT(self) -> str:
        return self.system_prompt


    async def handle_request(self, db: AsyncSession, user: User, message: str) -> Dict[str, Any]:
        msg_lower = message.lower()
        structured_action: Optional[StructuredAction] = None

        # 1. Fetch real balances deterministically
        balance_summary = await LeaveService.get_balance_summary(db, user.id)
        balance_map = {b.leave_type.value: b.available_balance for b in balance_summary.balances}

        # Check if user wants to apply for leave
        apply_intent = any(w in msg_lower for w in ["apply", "take", "request", "book", "need"]) and any(w in msg_lower for w in ["leave", "day off", "vacation", "sick"])
        
        # Detect leave type mentioned
        detected_type = LeaveType.CL
        if "earned" in msg_lower or "el" in msg_lower or "privilege" in msg_lower:
            detected_type = LeaveType.EL
        elif "sick" in msg_lower or "sl" in msg_lower or "medical" in msg_lower:
            detected_type = LeaveType.SL
        elif "without pay" in msg_lower or "lwp" in msg_lower:
            detected_type = LeaveType.LWP

        if apply_intent:
            # Propose structured action with dates (e.g. tomorrow or specified)
            start_d = date.today() + timedelta(days=1)
            end_d = start_d
            
            # Check for multi-day mentions like "2 days" or "3 days"
            day_match = re.search(r"(\d+)\s*days?", msg_lower)
            if day_match:
                count = int(day_match.group(1))
                end_d = start_d + timedelta(days=max(0, count - 1))

            avail = balance_map.get(detected_type.value, 0.0)
            req_days = float((end_d - start_d).days + 1)

            type_names = {
                LeaveType.CL: "Casual Leave (CL)",
                LeaveType.EL: "Earned Leave (EL)",
                LeaveType.SL: "Sick Leave (SL)",
                LeaveType.LWP: "Leave Without Pay (LWP)"
            }
            type_display = type_names.get(detected_type, detected_type.value)

            first_name = user.full_name.split()[0] if user.full_name else "there"

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
                f"• Earned Leave (EL): {balance_map.get('EL', 0.0)} days (Accrues monthly; max accumulation 45 days)\n"
                f"• Casual Leave (CL): {balance_map.get('CL', 0.0)} days (8 days statutory; non-cumulative)\n"
                f"• Sick Leave (SL): {balance_map.get('SL', 0.0)} days (Cumulative up to 20 days)\n"
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

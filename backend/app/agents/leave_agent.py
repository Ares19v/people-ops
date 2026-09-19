import re
from datetime import date, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.leave import LeaveType
from app.services.leave_service import LeaveService
from app.schemas.agent import StructuredAction
from app.agents.llm_provider import get_llm_provider

class LeaveAgent:
    """Agent responsible for leave balance querying, leave application assistance, and rule validation."""

    SYSTEM_PROMPT = """You are the Leave Management Agent for Intelera Technologies.
Your responsibilities:
- Show accurate leave balances and history retrieved from the authoritative database.
- Assist users in applying for Earned Leave (EL), Casual Leave (CL), Sick Leave (SL), or Leave Without Pay (LWP).
- Enforce validation rules: date order, no overlapping leaves, balance sufficiency, and manager approval workflows.
- Never invent or fabricate balances or policy rules; always use retrieved authoritative facts.
- Present clear explanations for all actions.
"""

    def __init__(self):
        self.llm = get_llm_provider()

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

            if detected_type != LeaveType.LWP and req_days > avail:
                reply = (
                    f"⚠️ **Insufficient Balance Alert**: You requested {req_days} day(s) of {detected_type.value}, "
                    f"but your current available balance is **{avail} day(s)**. "
                    f"You may apply for Leave Without Pay (LWP) or adjust the requested duration."
                )
            else:
                reply = (
                    f"I have prepared your leave application for **{detected_type.value}** from "
                    f"**{start_d.strftime('%b %d, %Y')}** to **{end_d.strftime('%b %d, %Y')}** ({req_days} day(s)).\n"
                    f"- Current Available Balance: **{avail} days**\n"
                    f"- Approver: Your designated Reporting Manager\n\n"
                    f"Please confirm to submit this application."
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
            # Informational balance reply
            reply = (
                f"### 📋 Current Verified Leave Balances for {user.full_name}:\n"
                f"- **Earned Leave (EL)**: {balance_map.get('EL', 0.0)} days (Accrues monthly; max accumulation 45 days)\n"
                f"- **Casual Leave (CL)**: {balance_map.get('CL', 0.0)} days (8 days statutory; non-cumulative)\n"
                f"- **Sick Leave (SL)**: {balance_map.get('SL', 0.0)} days (Cumulative up to 20 days)\n"
                f"- **Leave Without Pay (LWP)**: Uncapped (Discretionary management approval)\n\n"
                f"Would you like me to prepare a leave application for any of these dates?"
            )

        return {
            "response": reply,
            "agent_routed": "LEAVE_AGENT",
            "structured_action": structured_action,
            "citations": []
        }

leave_agent = LeaveAgent()

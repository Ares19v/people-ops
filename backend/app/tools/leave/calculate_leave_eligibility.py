"""Tool: calculate_leave_eligibility (Google ADK compatible tool)."""

import logging
from datetime import date
from typing import Any, Dict

from app.core.database import db_session
from app.core.logging_config import log_tool_call
from app.services.leave_service import LeaveService

logger = logging.getLogger(__name__)


@log_tool_call
async def calculate_leave_eligibility(
    user_id: str,
    leave_type: str,
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    """Calculate working days and check if employee has sufficient balance for proposed leave.

    Args:
        user_id: Unique UUID of the employee.
        leave_type: Code of leave ("CL", "EL", "SL", "LWP").
        start_date: Start date formatted as YYYY-MM-DD.
        end_date: End date formatted as YYYY-MM-DD.

    Returns:
        Dict with duration, balance status, and eligibility flag.
    """
    try:
        s_date = date.fromisoformat(start_date)
        e_date = date.fromisoformat(end_date)
        if e_date < s_date:
            return {"error": "end_date cannot precede start_date."}

        total_days = float((e_date - s_date).days + 1)

        async with db_session() as session:
            summary = await LeaveService.get_balance_summary(session, user_id=user_id)
            avail = 0.0
            for b in summary.balances:
                if b.leave_type.value == leave_type.upper():
                    avail = b.available_balance
                    break

            is_eligible = (leave_type.upper() == "LWP") or (avail >= total_days)

            return {
                "leave_type": leave_type.upper(),
                "start_date": start_date,
                "end_date": end_date,
                "requested_days": total_days,
                "available_balance": avail,
                "is_eligible": is_eligible,
                "message": (
                    "Sufficient balance available."
                    if is_eligible
                    else f"Insufficient balance ({avail} available vs {total_days} requested)."
                ),
            }
    except Exception as exc:
        return {"error": f"Failed to calculate eligibility: {str(exc)}"}

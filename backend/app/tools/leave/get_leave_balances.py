"""Tool: get_leave_balances (Google ADK compatible tool)."""

import logging
from typing import Any, Dict

from app.core.database import db_session
from app.core.logging_config import log_tool_call
from app.services.leave_service import LeaveService

logger = logging.getLogger(__name__)


@log_tool_call
async def get_leave_balances(user_id: str) -> Dict[str, Any]:
    """Retrieve real-time available leave balances (EL, CL, SL, LWP) for an employee.

    Args:
        user_id: Unique UUID/ID of the employee.

    Returns:
        Dict mapping leave types to available days, or {"error": "..."}.
    """
    try:
        async with db_session() as session:
            summary = await LeaveService.get_balance_summary(session, user_id=user_id)
            balances = {
                b.leave_type.value: {
                    "allocated": b.total_allocated,
                    "used": b.used_days,
                    "pending": b.pending_days,
                    "available": b.available_balance,
                }
                for b in summary.balances
            }
            return {
                "user_id": user_id,
                "balances": balances,
                "status": "success",
            }
    except Exception as exc:
        return {"error": f"Failed to fetch leave balances: {str(exc)}"}

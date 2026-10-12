"""Tool: apply_leave (Google ADK compatible tool)."""

import logging
from datetime import date
from typing import Any, Dict

from app.core.database import db_session
from app.core.logging_config import log_tool_call
from app.core.id_generator import generate_entity_id
from app.models.leave import LeaveApplication, LeaveStatus, LeaveType

logger = logging.getLogger(__name__)


@log_tool_call
async def apply_leave(
    user_id: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    reason: str,
) -> Dict[str, Any]:
    """Submit a formal leave application on behalf of the employee.

    Args:
        user_id: Unique UUID of the employee.
        leave_type: Type of leave ("CL", "EL", "SL", "LWP").
        start_date: Start date formatted as YYYY-MM-DD.
        end_date: End date formatted as YYYY-MM-DD.
        reason: Reason for taking leave.

    Returns:
        Dict with created application details or error.
    """
    try:
        s_date = date.fromisoformat(start_date)
        e_date = date.fromisoformat(end_date)
        days = float((e_date - s_date).days + 1)

        async with db_session() as session:
            lt_enum = getattr(LeaveType, leave_type.upper(), LeaveType.CL)
            app_id = generate_entity_id("leave", user_id)
            application = LeaveApplication(
                id=app_id,
                user_id=user_id,
                leave_type=lt_enum,
                start_date=s_date,
                end_date=e_date,
                total_days=days,
                reason=reason,
                status=LeaveStatus.SUBMITTED,
            )
            session.add(application)
            await session.commit()
            await session.refresh(application)

            return {
                "application_id": application.id,
                "leave_type": application.leave_type.value,
                "days": application.days,
                "start_date": str(application.start_date),
                "end_date": str(application.end_date),
                "status": application.status.value,
                "message": "Leave application submitted successfully for manager approval.",
            }
    except Exception as exc:
        return {"error": f"Failed to submit leave application: {str(exc)}"}

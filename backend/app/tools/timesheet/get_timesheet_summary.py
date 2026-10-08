"""Tool: get_timesheet_summary (Google ADK compatible tool)."""

import logging
from typing import Any, Dict

from sqlalchemy import case, func
from sqlalchemy.future import select

from app.core.database import db_session
from app.core.logging_config import log_tool_call
from app.models.timesheet import TimesheetEntry

logger = logging.getLogger(__name__)


@log_tool_call
async def get_timesheet_summary(user_id: str) -> Dict[str, Any]:
    """Retrieve logged work hours and billable breakdown for an employee.

    Args:
        user_id: Unique UUID of the employee.

    Returns:
        Dict with total_hours, billable_hours, non_billable_hours, and status.
    """
    try:
        async with db_session() as session:
            stmt = select(
                func.coalesce(func.sum(TimesheetEntry.hours), 0.0),
                func.coalesce(func.sum(case((TimesheetEntry.is_billable == True, TimesheetEntry.hours), else_=0.0)), 0.0),
            ).filter(TimesheetEntry.user_id == user_id)

            res = await session.execute(stmt)
            row = res.first()
            total_hours = float(row[0]) if row else 0.0
            billable_hours = float(row[1]) if row else 0.0
            non_billable_hours = total_hours - billable_hours

            return {
                "user_id": user_id,
                "total_hours": total_hours,
                "billable_hours": billable_hours,
                "non_billable_hours": non_billable_hours,
                "billable_percentage": round((billable_hours / total_hours * 100), 1) if total_hours > 0 else 0.0,
                "status": "success",
            }
    except Exception as exc:
        return {"error": f"Failed to retrieve timesheet summary: {str(exc)}"}

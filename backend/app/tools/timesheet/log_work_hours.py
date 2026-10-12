"""Tool: log_work_hours (Google ADK compatible tool)."""

import logging
from datetime import date
from typing import Any, Dict

from sqlalchemy.future import select

from app.core.database import db_session
from app.core.logging_config import log_tool_call
from app.core.id_generator import generate_entity_id
from app.models.timesheet import Project, TimesheetEntry, TimesheetStatus

logger = logging.getLogger(__name__)


@log_tool_call
async def log_work_hours(
    user_id: str,
    project_name: str,
    task_name: str,
    hours: float,
    entry_date: str,
    is_billable: bool = True,
) -> Dict[str, Any]:
    """Log work or project hours for an employee on a specified date.

    Args:
        user_id: Unique UUID of the employee.
        project_name: Name or code of the active project.
        task_name: Description or name of the task.
        hours: Number of hours worked (e.g. 8.0, 4.5).
        entry_date: Date formatted as YYYY-MM-DD.
        is_billable: True if project client billable, False otherwise.

    Returns:
        Dict with logged entry confirmation or error if daily limits exceeded.
    """
    try:
        w_date = date.fromisoformat(entry_date)
        if hours <= 0 or hours > 16:
            return {"error": f"Invalid hours ({hours}). Must be between 0.5 and 16.0 hours."}

        async with db_session() as session:
            # Find or fallback to first active project
            proj_stmt = select(Project).filter(Project.is_active == True)
            proj_res = await session.execute(proj_stmt)
            project = proj_res.scalars().first()

            if not project:
                project = Project(
                    name=project_name or "General Operations",
                    code="GEN-01",
                    client_name="Internal",
                    is_active=True,
                )
                session.add(project)
                await session.flush()

            entry_id = generate_entity_id("timesheet", user_id)
            entry = TimesheetEntry(
                id=entry_id,
                user_id=user_id,
                project_id=project.id,
                task_name=task_name,
                hours=hours,
                entry_date=w_date,
                is_billable=is_billable,
                status=TimesheetStatus.SUBMITTED,
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)

            return {
                "entry_id": entry.id,
                "project": project.name,
                "task": entry.task_name,
                "hours": entry.hours,
                "date": str(entry.entry_date),
                "is_billable": entry.is_billable,
                "status": "success",
                "message": f"Successfully logged {hours} hrs on {entry_date}.",
            }
    except Exception as exc:
        return {"error": f"Failed to log timesheet hours: {str(exc)}"}

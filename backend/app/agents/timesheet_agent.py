import re
from datetime import date
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User, UserRole
from app.models.timesheet import Project
from app.services.timesheet_service import TimesheetService
from app.schemas.timesheet import TimesheetReportFilter
from app.schemas.agent import StructuredAction
from app.agents.llm_provider import get_llm_provider

class TimesheetAgent:
    """Agent assisting employees with time logging, submission, and managers with reporting."""

    SYSTEM_PROMPT = """You are the Timesheet Assistant for Antigravity Global Technologies.
Your responsibilities:
- Guide employees to accurately record project tasks, daily hours, and billable status.
- Enforce validation rules: max 16 hours/day, no duplicates, valid projects.
- Help managers summarize daily, weekly, and monthly hours and export CSVs.
"""

    def __init__(self):
        self.llm = get_llm_provider()

    async def handle_request(self, db: AsyncSession, user: User, message: str) -> Dict[str, Any]:
        msg_lower = message.lower()
        structured_action: Optional[StructuredAction] = None

        # Check if requesting reports or summary
        if "report" in msg_lower or "hours" in msg_lower or "summary" in msg_lower:
            filters = TimesheetReportFilter(user_id=user.id if user.role == UserRole.EMPLOYEE else None)
            summary = await TimesheetService.get_report_summary(db, filters, user)
            
            reply = (
                f"### ⏱️ Timesheet Summary ({'Personal' if user.role == UserRole.EMPLOYEE else 'Team'}):\n"
                f"- **Total Hours**: {summary.total_hours} hrs\n"
                f"- **Billable Hours**: {summary.billable_hours} hrs ({summary.total_hours and round(summary.billable_hours/summary.total_hours*100, 1)}%)\n"
                f"- **Non-Billable Hours**: {summary.non_billable_hours} hrs\n"
                f"- **Logged Entries**: {summary.entry_count}\n\n"
                f"You can view and export detailed records via the Timesheet Reports tab."
            )
            return {
                "response": reply,
                "agent_routed": "TIMESHEET_AGENT",
                "citations": [],
                "structured_action": None
            }

        # Check if intent is to log hours (e.g. "log 4 hours on project X for task Y")
        log_intent = any(w in msg_lower for w in ["log", "record", "enter", "track", "add"]) and "hour" in msg_lower
        if log_intent:
            # Extract hours
            hours_match = re.search(r"(\d+(\.\d+)?)\s*hours?", msg_lower)
            logged_hours = float(hours_match.group(1)) if hours_match else 8.0

            # Find an active project
            proj_stmt = select(Project).filter(Project.is_active == True)
            proj_res = await db.execute(proj_stmt)
            projects = proj_res.scalars().all()
            project = projects[0] if projects else None

            if not project:
                reply = "No active projects found to log hours against. Please contact your Project Administrator."
            else:
                reply = (
                    f"I have prepared a timesheet entry for **{logged_hours} hours** on project **{project.name}** "
                    f"(Task: *General Development*, Date: {date.today()}).\n"
                    f"Please confirm to submit."
                )
                structured_action = StructuredAction(
                    action_type="TIMESHEET_LOG",
                    action_payload={
                        "project_id": project.id,
                        "task_name": "Development & Code Review",
                        "entry_date": str(date.today()),
                        "hours": logged_hours,
                        "is_billable": True,
                        "notes": f"Logged via AI Assistant: {message[:100]}"
                    },
                    requires_confirmation=True,
                    executed=False
                )
        else:
            reply = (
                "Here is how I can help with Timesheets:\n"
                "1. **Log Hours**: Tell me how many hours you worked on a project.\n"
                "2. **View Reports**: Ask for your daily, weekly, or monthly logged hours.\n"
                "3. **Submission Guidelines**: Monday 12:00 PM submission deadline."
            )

        return {
            "response": reply,
            "agent_routed": "TIMESHEET_AGENT",
            "citations": [],
            "structured_action": structured_action
        }

timesheet_agent = TimesheetAgent()

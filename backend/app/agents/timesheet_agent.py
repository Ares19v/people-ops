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
from google.adk.agents import Agent
from app.core.llm_bridge import get_llm_model
from app.tools.timesheet.get_timesheet_summary import get_timesheet_summary
from app.tools.timesheet.log_work_hours import log_work_hours
from app.services.langfuse_prompt_service import langfuse_prompt_service

# ── Google ADK Specialist Sub-Agent Definition ─────────────────────────────────

timesheet_adk_agent = Agent(
    name="timesheet_agent",
    model=get_llm_model(),
    description=(
        "Specialist Timesheet & Time Tracking Agent. Responsible for fetching timesheet "
        "summaries, logging project hours, and enforcing daily/weekly overtime boundaries."
    ),
    instruction=langfuse_prompt_service.get_prompt("timesheet-subagent", label="live"),
    tools=[
        get_timesheet_summary,
        log_work_hours,
    ],
)


class TimesheetAgent:
    """Agent assisting employees with time logging, submission, and managers with reporting."""

    def __init__(self):
        self.llm = get_llm_provider()

    @property
    def system_prompt(self) -> str:
        return langfuse_prompt_service.get_prompt("timesheet-subagent", label="live")

    @property
    def SYSTEM_PROMPT(self) -> str:
        return self.system_prompt


    async def handle_request(self, db: AsyncSession, user: User, message: str) -> Dict[str, Any]:
        msg_lower = message.lower()
        structured_action: Optional[StructuredAction] = None

        # Check if employee asks about working/logging beyond statutory limits (e.g. 12 hours, >11 hours)
        hours_mentioned = re.search(r"(\d+(\.\d+)?)\s*hours?", msg_lower)
        num_hours = float(hours_mentioned.group(1)) if hours_mentioned else 0.0

        if num_hours > 11.0 and any(w in msg_lower for w in ["log", "work", "worked", "yesterday", "can i", "permit"]):
            reply = (
                f"⚠️ Statutory Limit Violation Notice (Maharashtra Shops & Establishments Act, 2017 - Section 14):\n\n"
                f"You cannot log {num_hours:g} hours for a single day. Under Section 14(2), no employee is permitted to work beyond a mandatory daily hard ceiling of **11 hours** (inclusive of standard work and overtime).\n\n"
                f"• Statutory Daily Hard Ceiling: 11 hours maximum per day (Section 14(2))\n"
                f"• Standard Working Limit: Up to 9 hours/day (Section 13)\n"
                f"• Overtime Compensation: Hours between 9 and 11 hours qualify for statutory double wages at 2.0x (Section 14(1))\n"
                f"• Statutory Prohibition: Working {num_hours:g} hours in a single day exceeds legal thresholds and cannot be approved.\n\n"
                f"Please cap your daily log to a maximum of 11 hours, or split the extra hours across eligible working days."
            )
            return {
                "response": reply,
                "agent_routed": "TIMESHEET_SUBAGENT",
                "citations": [],
                "structured_action": None
            }

        # Check if asking about overtime rules or statutory limits
        if "overtime" in msg_lower and not ("log" in msg_lower and "hour" in msg_lower):
            reply = (
                "Under the Maharashtra Shops and Establishments Act, 2017 (Section 13 & 14) and Company Working Hours Policy:\n\n"
                "• Standard Hours: 8 hours/day, 40 hours/week\n"
                "• Overtime Rate: Work exceeding 9 hours/day or 48 hours/week is compensable at twice the ordinary wage rate (2.0x)\n"
                "• Daily Overtime Cap: Total working hours including overtime cannot exceed 11 hours per day per Section 14\n"
                "• Quarterly Overtime Limit: Capped at 125 hours per quarter under statutory mandates."
            )
            return {
                "response": reply,
                "agent_routed": "TIMESHEET_SUBAGENT",
                "citations": [],
                "structured_action": None
            }

        # Check if intent is to log hours (e.g. "log 4 hours on project X for task Y")
        log_intent = any(w in msg_lower for w in ["log", "record", "enter", "track", "add"]) and "hour" in msg_lower
        if not log_intent and any(w in msg_lower for w in ["report", "summary", "my hours", "show hours", "view timesheet"]):
            filters = TimesheetReportFilter(user_id=user.id if user.role == UserRole.EMPLOYEE else None)
            summary = await TimesheetService.get_report_summary(db, filters, user)
            
            first_name = user.full_name.split()[0] if user.full_name else "there"
            pct = round(summary.billable_hours/summary.total_hours*100, 1) if summary.total_hours else 0
            reply = (
                f"Here is your timesheet summary for this week, {first_name}:\n\n"
                f"• Total Hours: {summary.total_hours} hrs\n"
                f"• Billable Hours: {summary.billable_hours} hrs ({pct}%)\n"
                f"• Non-Billable Hours: {summary.non_billable_hours} hrs\n"
                f"• Logged Entries: {summary.entry_count}\n\n"
                f"You can view and export detailed records via the Timesheet Reports tab."
            )
            return {
                "response": reply,
                "agent_routed": "TIMESHEET_SUBAGENT",
                "citations": [],
                "structured_action": None
            }
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
                    f"I have prepared a timesheet entry for {logged_hours} hours on project {project.name} "
                    f"(Task: General Development, Date: {date.today()}).\n"
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
                "Here is how I can help with Timesheets:\n\n"
                "• Log Hours: Tell me how many hours you worked on a project\n"
                "• View Reports: Ask for your daily, weekly, or monthly logged hours\n"
                "• Submission Guidelines: Monday 12:00 PM submission deadline"
            )

        return {
            "response": reply,
            "agent_routed": "TIMESHEET_AGENT",
            "citations": [],
            "structured_action": structured_action
        }

timesheet_agent = TimesheetAgent()

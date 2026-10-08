"""
PeopleOps — Pure Async HR Tools for Google ADK Agents
======================================================
Follows Google ADK standards:
  • Plain `async def` with typed signatures and docstrings
  • Decoupled: One tool per file under domain packages:
      app/tools/leave/
      app/tools/timesheet/
      app/tools/health/
      app/tools/policy/
      app/tools/zoho/
  • Re-exported here for centralized compatibility.
"""
from app.tools.leave.get_leave_balances import get_leave_balances
from app.tools.leave.calculate_leave_eligibility import calculate_leave_eligibility
from app.tools.leave.apply_leave import apply_leave

# Timesheet tools
from app.tools.timesheet.get_timesheet_summary import get_timesheet_summary
from app.tools.timesheet.log_work_hours import log_work_hours

# Health tools
from app.tools.health.get_occupational_health_guidelines import get_occupational_health_guidelines

# Policy & Statutory tools
from app.tools.policy.check_statutory_compliance import check_statutory_compliance
from app.tools.policy.query_company_policy import query_company_policy

# Zoho tools
from app.tools.zoho.sync_zoho_leave_records import sync_zoho_leave_records

__all__ = [
    # Leave
    "get_leave_balances",
    "calculate_leave_eligibility",
    "apply_leave",
    # Timesheet
    "get_timesheet_summary",
    "log_work_hours",
    # Health
    "get_occupational_health_guidelines",
    # Policy
    "check_statutory_compliance",
    "query_company_policy",
    # Zoho
    "sync_zoho_leave_records",
]

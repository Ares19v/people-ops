import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from app.models.user import User, UserRole
from app.models.timesheet import Project, TimesheetEntry, TimesheetStatus
from app.schemas.timesheet import TimesheetEntryCreate, TimesheetReportSummary, TimesheetEntryResponse
from app.services.timesheet_service import TimesheetService

def test_generate_csv_format():
    report = TimesheetReportSummary(
        total_hours=16.0,
        billable_hours=16.0,
        non_billable_hours=0.0,
        entry_count=2,
        entries=[
            TimesheetEntryResponse(
                id="entry-1",
                user_id="user-1",
                employee_name="Aarav Sharma",
                project_id="proj-1",
                project_name="Core Banking",
                task_name="Backend APIs",
                entry_date=date(2026, 3, 1),
                hours=8.0,
                is_billable=True,
                notes="Developed endpoints",
                status=TimesheetStatus.APPROVED,
                approver_id="mgr-1",
                rejection_reason=None,
                created_at=date(2026, 3, 1)
            ),
            TimesheetEntryResponse(
                id="entry-2",
                user_id="user-1",
                employee_name="Aarav Sharma",
                project_id="proj-1",
                project_name="Core Banking",
                task_name="Unit Testing",
                entry_date=date(2026, 3, 2),
                hours=8.0,
                is_billable=True,
                notes="Tested coverage",
                status=TimesheetStatus.SUBMITTED,
                approver_id=None,
                rejection_reason=None,
                created_at=date(2026, 3, 2)
            )
        ]
    )

    csv_output = TimesheetService.generate_csv(report)
    assert "Entry ID,Employee,Project,Task,Date,Hours,Billable,Status,Notes" in csv_output
    assert "entry-1,Aarav Sharma,Core Banking,Backend APIs,2026-03-01,8.0,Yes,APPROVED,Developed endpoints" in csv_output
    assert "entry-2,Aarav Sharma,Core Banking,Unit Testing,2026-03-02,8.0,Yes,SUBMITTED,Tested coverage" in csv_output

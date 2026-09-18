# TimesheetService

> God node · 25 connections · `backend/app/services/timesheet_service.py`

**Community:** [timesheets.py](timesheets.py.md)

## Connections by Relation

### contains
- timesheet_service.py `EXTRACTED`

### imports
- [timesheets.py](timesheets.py.md) `EXTRACTED`
- reports.py `EXTRACTED`
- timesheet_agent.py `EXTRACTED`
- test_timesheet_service.py `EXTRACTED`

### method
- .get_report_summary() `EXTRACTED`
- .log_entry() `EXTRACTED`
- .decide_entries() `EXTRACTED`
- .generate_csv() `EXTRACTED`

### uses
- [User](User.md) `INFERRED`
- [UserRole](UserRole.md) `INFERRED`
- [AuditLog](AuditLog.md) `INFERRED`
- [TimesheetStatus](TimesheetStatus.md) `INFERRED`
- TimesheetReportFilter `INFERRED`
- Project `INFERRED`
- TimesheetEntry `INFERRED`
- TimesheetAgent `INFERRED`
- export_timesheet_csv() `INFERRED`
- TimesheetReportSummary `INFERRED`
- TimesheetEntryResponse `INFERRED`
- get_timesheet_report() `INFERRED`
- TimesheetEntryCreate `INFERRED`
- batch_decide_timesheets() `INFERRED`
- log_time_entry() `INFERRED`
- test_generate_csv_format() `INFERRED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*
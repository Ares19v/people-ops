# timesheets.py

> 56 nodes · cohesion 0.10

## Key Concepts

- **timesheets.py** (25 connections) — `backend/app/api/v1/timesheets.py`
- **TimesheetService** (25 connections) — `backend/app/services/timesheet_service.py`
- **typing** (25 connections)
- **timesheet_service.py** (23 connections) — `backend/app/services/timesheet_service.py`
- **reports.py** (20 connections) — `backend/app/api/v1/reports.py`
- **timesheet_agent.py** (19 connections) — `backend/app/agents/timesheet_agent.py`
- **auth_service.py** (17 connections) — `backend/app/services/auth_service.py`
- **test_timesheet_service.py** (17 connections) — `backend/tests/test_timesheet_service.py`
- **TimesheetStatus** (15 connections) — `backend/app/models/timesheet.py`
- **sqlalchemy_ext_asyncio** (15 connections)
- **TimesheetReportFilter** (13 connections) — `backend/app/schemas/timesheet.py`
- **Project** (12 connections) — `backend/app/models/timesheet.py`
- **schemas/timesheet.py** (12 connections) — `backend/app/schemas/timesheet.py`
- **TimesheetEntry** (11 connections) — `backend/app/models/timesheet.py`
- **get_current_user()** (11 connections) — `backend/app/services/auth_service.py`
- **sqlalchemy_future** (11 connections)
- **TimesheetAgent** (10 connections) — `backend/app/agents/timesheet_agent.py`
- **export_timesheet_csv()** (10 connections) — `backend/app/api/v1/reports.py`
- **TimesheetEntryResponse** (10 connections) — `backend/app/schemas/timesheet.py`
- **TimesheetReportSummary** (10 connections) — `backend/app/schemas/timesheet.py`
- **get_timesheet_report()** (9 connections) — `backend/app/api/v1/reports.py`
- **get_db()** (9 connections) — `backend/app/core/database.py`
- **TimesheetEntryCreate** (9 connections) — `backend/app/schemas/timesheet.py`
- **.get_report_summary()** (9 connections) — `backend/app/services/timesheet_service.py`
- **app_models_timesheet** (8 connections)
- *... and 31 more nodes in this community*

## Relationships

- [User](User.md) (33 shared connections)
- [UserRole](UserRole.md) (27 shared connections)
- [app_models_user](app_models_user.md) (27 shared connections)
- [models/__init__.py](models-__init__.py.md) (26 shared connections)
- [leaves.py](leaves.py.md) (10 shared connections)
- [security.py](security.py.md) (7 shared connections)
- [main.py](main.py.md) (6 shared connections)
- [get_llm_provider](get_llm_provider.md) (3 shared connections)
- [test_api_endpoints.py](test_api_endpoints.py.md) (1 shared connections)

## Source Files

- `backend/app/agents/timesheet_agent.py`
- `backend/app/api/v1/reports.py`
- `backend/app/api/v1/timesheets.py`
- `backend/app/core/database.py`
- `backend/app/models/timesheet.py`
- `backend/app/schemas/timesheet.py`
- `backend/app/services/auth_service.py`
- `backend/app/services/timesheet_service.py`
- `backend/tests/test_timesheet_service.py`

## Audit Trail

- EXTRACTED: 262 (87%)
- INFERRED: 39 (13%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*
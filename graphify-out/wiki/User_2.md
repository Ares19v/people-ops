# User

> God node · 65 connections · `backend/app/models/user.py`

**Community:** [User](User.md)

## Connections by Relation

### calls
- [seed_initial_data()](seed_initial_data.md) `EXTRACTED`
- run() `INFERRED`

### contains
- user.py `EXTRACTED`

### imports
- v1/onboarding.py `EXTRACTED`
- [leaves.py](leaves.py.md) `EXTRACTED`
- [timesheets.py](timesheets.py.md) `EXTRACTED`
- [models/__init__.py](models-__init__.py.md) `EXTRACTED`
- v1/auth.py `EXTRACTED`
- onboarding_service.py `EXTRACTED`
- timesheet_service.py `EXTRACTED`
- seed_data.py `EXTRACTED`
- reports.py `EXTRACTED`
- leave_service.py `EXTRACTED`
- timesheet_agent.py `EXTRACTED`
- auth_service.py `EXTRACTED`
- test_timesheet_service.py `EXTRACTED`
- orchestrator.py `EXTRACTED`
- test_leave_service.py `EXTRACTED`
- leave_agent.py `EXTRACTED`
- agents.py `EXTRACTED`
- policy_agent.py `EXTRACTED`
- v1/policy.py `EXTRACTED`

### inherits
- Base `EXTRACTED`

### references
- .apply_leave() `EXTRACTED`
- .get_report_summary() `EXTRACTED`
- .upload_document() `EXTRACTED`
- .handle_request() `EXTRACTED`
- .confirm_onboarding() `EXTRACTED`
- .log_entry() `EXTRACTED`
- .handle_request() `EXTRACTED`
- .decide_leave() `EXTRACTED`
- .decide_entries() `EXTRACTED`
- .create_or_update_employee() `EXTRACTED`
- .handle_request() `EXTRACTED`
- .process_message() `EXTRACTED`

### uses
- [LeaveService](LeaveService.md) `INFERRED`
- [TimesheetService](TimesheetService.md) `INFERRED`
- [OnboardingService](OnboardingService.md) `INFERRED`
- get_current_user() `INFERRED`
- export_timesheet_csv() `INFERRED`
- TimesheetAgent `INFERRED`
- upload_onboarding_document() `INFERRED`
- get_timesheet_report() `INFERRED`
- mock_login() `INFERRED`
- confirm_onboarding_profile() `INFERRED`
- initiate_employee_onboarding() `INFERRED`
- batch_decide_timesheets() `INFERRED`
- LeaveAgent `INFERRED`
- login_for_access_token() `INFERRED`
- test_leave_application_and_overlap_validation() `INFERRED`
- apply_for_leave() `INFERRED`
- decide_leave_application() `INFERRED`
- get_my_leave_balances() `INFERRED`
- list_leave_applications() `INFERRED`
- extract_resume_details() `INFERRED`
- *…and 10 more `uses` connection(s) not listed (lowest-degree first to go)*

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*
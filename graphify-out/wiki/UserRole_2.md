# UserRole

> God node · 36 connections · `backend/app/models/user.py`

**Community:** [UserRole](UserRole.md)

## Connections by Relation

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
- test_leave_service.py `EXTRACTED`
- test_auth_rbac.py `EXTRACTED`
- schemas/auth.py `EXTRACTED`

### inherits
- str `EXTRACTED`

### uses
- [LeaveService](LeaveService.md) `INFERRED`
- [TimesheetService](TimesheetService.md) `INFERRED`
- [OnboardingService](OnboardingService.md) `INFERRED`
- [seed_initial_data()](seed_initial_data.md) `INFERRED`
- TimesheetAgent `INFERRED`
- mock_login() `INFERRED`
- confirm_onboarding_profile() `INFERRED`
- initiate_employee_onboarding() `INFERRED`
- batch_decide_timesheets() `INFERRED`
- get_my_leave_balances() `INFERRED`
- list_leave_applications() `INFERRED`
- extract_resume_details() `INFERRED`
- TokenResponse `INFERRED`
- require_role() `INFERRED`
- MockLoginRequest `INFERRED`
- UserResponse `INFERRED`
- test_jwt_token_generation_and_decode() `INFERRED`
- call_api() `INFERRED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*
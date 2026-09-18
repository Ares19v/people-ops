# AuditLog

> God node · 16 connections · `backend/app/models/user.py`

**Community:** [User](User.md)

## Connections by Relation

### calls
- .apply_leave() `EXTRACTED`
- .upload_document() `EXTRACTED`
- .confirm_onboarding() `EXTRACTED`
- .log_entry() `EXTRACTED`
- .decide_leave() `EXTRACTED`
- .create_or_update_employee() `EXTRACTED`
- .decide_entries() `EXTRACTED`

### contains
- user.py `EXTRACTED`

### imports
- [models/__init__.py](models-__init__.py.md) `EXTRACTED`
- onboarding_service.py `EXTRACTED`
- timesheet_service.py `EXTRACTED`
- leave_service.py `EXTRACTED`

### inherits
- Base `EXTRACTED`

### uses
- [LeaveService](LeaveService.md) `INFERRED`
- [TimesheetService](TimesheetService.md) `INFERRED`
- [OnboardingService](OnboardingService.md) `INFERRED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*
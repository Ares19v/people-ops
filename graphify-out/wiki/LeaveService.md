# LeaveService

> God node · 25 connections · `backend/app/services/leave_service.py`

**Community:** [leaves.py](leaves.py.md)

## Connections by Relation

### contains
- leave_service.py `EXTRACTED`

### imports
- [leaves.py](leaves.py.md) `EXTRACTED`
- test_leave_service.py `EXTRACTED`
- leave_agent.py `EXTRACTED`

### method
- .apply_leave() `EXTRACTED`
- .get_balance_summary() `EXTRACTED`
- .decide_leave() `EXTRACTED`
- .get_or_create_user_balances() `EXTRACTED`
- .check_leave_overlap() `EXTRACTED`

### uses
- [User](User.md) `INFERRED`
- [UserRole](UserRole.md) `INFERRED`
- [AuditLog](AuditLog.md) `INFERRED`
- [LeaveType](LeaveType.md) `INFERRED`
- LeaveStatus `INFERRED`
- LeaveApplyRequest `INFERRED`
- LeaveApplication `INFERRED`
- LeaveBalance `INFERRED`
- LeaveAgent `INFERRED`
- test_leave_application_and_overlap_validation() `INFERRED`
- apply_for_leave() `INFERRED`
- decide_leave_application() `INFERRED`
- get_my_leave_balances() `INFERRED`
- LeaveBalanceSummary `INFERRED`
- LeaveBalanceItem `INFERRED`
- test_invalid_date_range() `INFERRED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*
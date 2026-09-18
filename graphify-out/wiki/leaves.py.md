# leaves.py

> 36 nodes · cohesion 0.17

## Key Concepts

- **leaves.py** (25 connections) — `backend/app/api/v1/leaves.py`
- **LeaveService** (25 connections) — `backend/app/services/leave_service.py`
- **leave_service.py** (20 connections) — `backend/app/services/leave_service.py`
- **LeaveType** (16 connections) — `backend/app/models/leave.py`
- **test_leave_service.py** (16 connections) — `backend/tests/test_leave_service.py`
- **LeaveStatus** (13 connections) — `backend/app/models/leave.py`
- **schemas/leave.py** (12 connections) — `backend/app/schemas/leave.py`
- **LeaveApplyRequest** (12 connections) — `backend/app/schemas/leave.py`
- **LeaveApplication** (11 connections) — `backend/app/models/leave.py`
- **.apply_leave()** (11 connections) — `backend/app/services/leave_service.py`
- **test_leave_application_and_overlap_validation()** (8 connections) — `backend/tests/test_leave_service.py`
- **app_models_leave** (7 connections)
- **apply_for_leave()** (7 connections) — `backend/app/api/v1/leaves.py`
- **decide_leave_application()** (7 connections) — `backend/app/api/v1/leaves.py`
- **get_my_leave_balances()** (7 connections) — `backend/app/api/v1/leaves.py`
- **list_leave_applications()** (7 connections) — `backend/app/api/v1/leaves.py`
- **LeaveBalanceItem** (7 connections) — `backend/app/schemas/leave.py`
- **LeaveBalanceSummary** (7 connections) — `backend/app/schemas/leave.py`
- **.get_balance_summary()** (7 connections) — `backend/app/services/leave_service.py`
- **test_invalid_date_range()** (7 connections) — `backend/tests/test_leave_service.py`
- **LeaveApplicationResponse** (6 connections) — `backend/app/schemas/leave.py`
- **.decide_leave()** (6 connections) — `backend/app/services/leave_service.py`
- **LeaveDecisionRequest** (5 connections) — `backend/app/schemas/leave.py`
- **BaseModel** (5 connections)
- **.check_leave_overlap()** (5 connections) — `backend/app/services/leave_service.py`
- *... and 11 more nodes in this community*

## Relationships

- [models/__init__.py](models-__init__.py.md) (24 shared connections)
- [User](User.md) (16 shared connections)
- [UserRole](UserRole.md) (13 shared connections)
- [app_models_user](app_models_user.md) (12 shared connections)
- [timesheets.py](timesheets.py.md) (10 shared connections)
- [main.py](main.py.md) (2 shared connections)
- [test_api_endpoints.py](test_api_endpoints.py.md) (1 shared connections)

## Source Files

- `backend/app/api/v1/leaves.py`
- `backend/app/models/leave.py`
- `backend/app/schemas/leave.py`
- `backend/app/services/leave_service.py`
- `backend/tests/test_leave_service.py`

## Audit Trail

- EXTRACTED: 144 (78%)
- INFERRED: 40 (22%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*
import pytest
from datetime import date, timedelta
from app.core.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.leave import LeaveType, LeaveStatus
from app.schemas.leave import LeaveApplyRequest
from app.services.leave_service import LeaveService
from sqlalchemy.future import select

@pytest.mark.asyncio
async def test_leave_application_and_overlap_validation():
    async with AsyncSessionLocal() as db:
        # Fetch seeded employee
        res = await db.execute(select(User).filter(User.email == "employee@intelera.corp"))
        employee = res.scalars().first()
        assert employee is not None

        # 1. Apply for 2 days of EL in April
        start = date(2026, 4, 10)
        end = date(2026, 4, 11)
        req = LeaveApplyRequest(
            leave_type=LeaveType.EL,
            start_date=start,
            end_date=end,
            reason="Spring conference attendance"
        )
        app = await LeaveService.apply_leave(db, employee, req)
        assert app.status == LeaveStatus.SUBMITTED
        assert app.total_days == 2.0

        # 2. Test overlap detection: try applying for overlapping date (April 11)
        overlap_req = LeaveApplyRequest(
            leave_type=LeaveType.CL,
            start_date=date(2026, 4, 11),
            end_date=date(2026, 4, 12),
            reason="Overlapping request"
        )
        with pytest.raises(Exception) as exc_info:
            await LeaveService.apply_leave(db, employee, overlap_req)
        assert "overlaps with an existing" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_invalid_date_range():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).filter(User.email == "employee@intelera.corp"))
        employee = res.scalars().first()

        req = LeaveApplyRequest(
            leave_type=LeaveType.CL,
            start_date=date(2026, 5, 10),
            end_date=date(2026, 5, 5), # End before start
            reason="Invalid dates"
        )
        with pytest.raises(Exception) as exc_info:
            await LeaveService.apply_leave(db, employee, req)
        assert "Start date cannot be after end date" in str(exc_info.value.detail)

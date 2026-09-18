from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.timesheet import TimesheetStatus
from app.schemas.timesheet import TimesheetReportFilter, TimesheetReportSummary
from app.services.auth_service import get_current_user
from app.services.timesheet_service import TimesheetService

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/timesheets", response_model=TimesheetReportSummary)
async def get_timesheet_report(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    user_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    status: Optional[TimesheetStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    filters = TimesheetReportFilter(
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        project_id=project_id,
        status=status
    )
    summary = await TimesheetService.get_report_summary(db, filters, current_user)
    return summary

@router.get("/timesheets/csv")
async def export_timesheet_csv(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    user_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    status: Optional[TimesheetStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    filters = TimesheetReportFilter(
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        project_id=project_id,
        status=status
    )
    summary = await TimesheetService.get_report_summary(db, filters, current_user)
    csv_data = TimesheetService.generate_csv(summary)

    filename = f"timesheets_export_{date.today().isoformat()}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

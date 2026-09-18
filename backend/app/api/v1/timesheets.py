from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.timesheet import Project, TimesheetEntry
from app.schemas.timesheet import (
    TimesheetEntryCreate, TimesheetEntryResponse, TimesheetDecisionRequest, ProjectResponse
)
from app.services.auth_service import get_current_user, require_role
from app.services.timesheet_service import TimesheetService

router = APIRouter(prefix="/timesheets", tags=["Timesheets"])

@router.get("/projects", response_model=List[ProjectResponse])
async def list_active_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Project).filter(Project.is_active == True)
    res = await db.execute(stmt)
    projects = res.scalars().all()
    return projects

@router.post("/entry", response_model=TimesheetEntryResponse)
async def log_time_entry(
    payload: TimesheetEntryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    entry = await TimesheetService.log_entry(db, current_user, payload)
    return entry

@router.post("/decide", response_model=List[TimesheetEntryResponse])
async def batch_decide_timesheets(
    payload: TimesheetDecisionRequest,
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    entries = await TimesheetService.decide_entries(
        db, current_user, payload.entry_ids, payload.decision, payload.rejection_reason
    )
    return entries

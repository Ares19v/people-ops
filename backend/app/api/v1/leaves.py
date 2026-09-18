from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.leave import LeaveApplication, LeaveStatus
from app.schemas.leave import (
    LeaveBalanceSummary, LeaveApplyRequest, LeaveApplicationResponse, LeaveDecisionRequest
)
from app.services.auth_service import get_current_user
from app.services.leave_service import LeaveService

router = APIRouter(prefix="/leaves", tags=["Leave Management"])

@router.get("/balances", response_model=LeaveBalanceSummary)
async def get_my_leave_balances(
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    target_id = current_user.id
    if user_id and user_id != current_user.id:
        if current_user.role not in [UserRole.HR_MANAGER, UserRole.ADMIN]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view another employee's balances.")
        target_id = user_id

    summary = await LeaveService.get_balance_summary(db, target_id)
    return summary

@router.post("/apply", response_model=LeaveApplicationResponse)
async def apply_for_leave(
    payload: LeaveApplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    application = await LeaveService.apply_leave(db, current_user, payload)
    return application

@router.get("/applications", response_model=List[LeaveApplicationResponse])
async def list_leave_applications(
    status_filter: Optional[LeaveStatus] = None,
    all_employees: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(LeaveApplication)
    
    if all_employees:
        if current_user.role not in [UserRole.HR_MANAGER, UserRole.ADMIN]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to view all employee leaves.")
    else:
        query = query.filter(LeaveApplication.user_id == current_user.id)

    if status_filter:
        query = query.filter(LeaveApplication.status == status_filter)

    query = query.order_by(LeaveApplication.applied_at.desc())
    res = await db.execute(query)
    apps = res.scalars().all()
    return apps

@router.post("/{application_id}/decide", response_model=LeaveApplicationResponse)
async def decide_leave_application(
    application_id: str,
    payload: LeaveDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    decided = await LeaveService.decide_leave(
        db, application_id, current_user, payload.decision, payload.comments
    )
    return decided

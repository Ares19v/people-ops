from datetime import date, datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_
from fastapi import HTTPException, status

from app.models.user import User, UserRole, AuditLog
from app.models.leave import LeaveBalance, LeaveApplication, LeaveType, LeaveStatus
from app.schemas.leave import LeaveApplyRequest, LeaveBalanceSummary, LeaveBalanceItem

class LeaveService:
    @staticmethod
    async def get_or_create_user_balances(db: AsyncSession, user_id: str, year: int = 2026) -> List[LeaveBalance]:
        stmt = select(LeaveBalance).filter(LeaveBalance.user_id == user_id, LeaveBalance.year == year)
        result = await db.execute(stmt)
        balances = result.scalars().all()
        
        if not balances:
            # Initialize default balances based on company policy & statutory minimums
            defaults = [
                (LeaveType.EL, 18.0, 0.0), # 18 days annual
                (LeaveType.CL, 8.0, 0.0),  # 8 days statutory
                (LeaveType.SL, 10.0, 0.0), # 10 days
                (LeaveType.LWP, 0.0, 0.0), # Uncapped
            ]
            new_balances = []
            for l_type, allocated, cf in defaults:
                lb = LeaveBalance(
                    user_id=user_id,
                    year=year,
                    leave_type=l_type,
                    total_allocated=allocated,
                    used_days=0.0,
                    pending_days=0.0,
                    carry_forwarded=cf
                )
                db.add(lb)
                new_balances.append(lb)
            await db.commit()
            return new_balances
        return list(balances)

    @staticmethod
    async def get_balance_summary(db: AsyncSession, user_id: str, year: int = 2026) -> LeaveBalanceSummary:
        balances = await LeaveService.get_or_create_user_balances(db, user_id, year)
        items = [
            LeaveBalanceItem(
                leave_type=b.leave_type,
                total_allocated=b.total_allocated,
                used_days=b.used_days,
                pending_days=b.pending_days,
                carry_forwarded=b.carry_forwarded,
                available_balance=b.available_balance
            )
            for b in balances
        ]
        return LeaveBalanceSummary(user_id=user_id, year=year, balances=items)

    @staticmethod
    async def check_leave_overlap(
        db: AsyncSession, user_id: str, start_date: date, end_date: date, exclude_id: Optional[str] = None
    ) -> bool:
        """Returns True if there is an overlapping leave application that is SUBMITTED or APPROVED."""
        query = select(LeaveApplication).filter(
            LeaveApplication.user_id == user_id,
            LeaveApplication.status.in_([LeaveStatus.SUBMITTED, LeaveStatus.APPROVED]),
            or_(
                and_(LeaveApplication.start_date <= start_date, LeaveApplication.end_date >= start_date),
                and_(LeaveApplication.start_date <= end_date, LeaveApplication.end_date >= end_date),
                and_(LeaveApplication.start_date >= start_date, LeaveApplication.end_date <= end_date)
            )
        )
        if exclude_id:
            query = query.filter(LeaveApplication.id != exclude_id)
        
        result = await db.execute(query)
        overlap = result.scalars().first()
        return overlap is not None

    @staticmethod
    async def apply_leave(
        db: AsyncSession, user: User, request: LeaveApplyRequest
    ) -> LeaveApplication:
        # 1. Date validation
        if request.start_date > request.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date range: Start date cannot be after end date."
            )
        
        # Calculate days (inclusive)
        total_days = float((request.end_date - request.start_date).days + 1)
        if total_days <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Total leave days must be at least 1 day."
            )
        
        # 2. Check overlap
        has_overlap = await LeaveService.check_leave_overlap(db, user.id, request.start_date, request.end_date)
        if has_overlap:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Leave application overlaps with an existing submitted or approved leave period."
            )
        
        # 3. Check balance (if not LWP)
        balances = await LeaveService.get_or_create_user_balances(db, user.id, request.start_date.year)
        target_balance = next((b for b in balances if b.leave_type == request.leave_type), None)
        
        if request.leave_type != LeaveType.LWP:
            if not target_balance or target_balance.available_balance < total_days:
                avail = target_balance.available_balance if target_balance else 0.0
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient {request.leave_type.value} balance. Required: {total_days}, Available: {avail}"
                )
            # Update pending days
            target_balance.pending_days += total_days
        
        # 4. Route to manager
        approver_id = user.manager_id
        if not approver_id:
            # If user has no direct manager, route to any HR_MANAGER or ADMIN
            hr_stmt = select(User).filter(User.role.in_([UserRole.HR_MANAGER, UserRole.ADMIN]), User.is_active == True)
            hr_res = await db.execute(hr_stmt)
            default_hr = hr_res.scalars().first()
            approver_id = default_hr.id if default_hr else None

        application = LeaveApplication(
            user_id=user.id,
            leave_type=request.leave_type,
            start_date=request.start_date,
            end_date=request.end_date,
            total_days=total_days,
            reason=request.reason,
            status=LeaveStatus.SUBMITTED,
            approver_id=approver_id
        )
        db.add(application)
        
        # Audit log
        audit = AuditLog(
            actor_id=user.id,
            action="LEAVE_APPLY",
            resource_type="leave_application",
            resource_id=application.id,
            details={
                "leave_type": request.leave_type.value,
                "total_days": total_days,
                "start_date": str(request.start_date),
                "end_date": str(request.end_date)
            }
        )
        db.add(audit)
        await db.commit()
        await db.refresh(application)
        return application

    @staticmethod
    async def decide_leave(
        db: AsyncSession, application_id: str, approver: User, decision: str, comments: Optional[str] = None
    ) -> LeaveApplication:
        stmt = select(LeaveApplication).filter(LeaveApplication.id == application_id)
        result = await db.execute(stmt)
        app = result.scalars().first()
        if not app:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave application not found.")
        
        if app.status != LeaveStatus.SUBMITTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot decide leave application with current status: {app.status.value}"
            )
        
        # Authorization check: approver must be designated approver, HR Manager, or Admin
        is_authorized = (
            approver.id == app.approver_id or
            approver.role in [UserRole.HR_MANAGER, UserRole.ADMIN]
        )
        if not is_authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: You are not authorized to approve or reject this leave application."
            )

        # Retrieve balance
        bal_stmt = select(LeaveBalance).filter(
            LeaveBalance.user_id == app.user_id,
            LeaveBalance.year == app.start_date.year,
            LeaveBalance.leave_type == app.leave_type
        )
        bal_res = await db.execute(bal_stmt)
        balance = bal_res.scalars().first()

        if decision == "APPROVE":
            app.status = LeaveStatus.APPROVED
            if balance and app.leave_type != LeaveType.LWP:
                balance.pending_days = max(0.0, balance.pending_days - app.total_days)
                balance.used_days += app.total_days
        elif decision == "REJECT":
            app.status = LeaveStatus.REJECTED
            if balance and app.leave_type != LeaveType.LWP:
                balance.pending_days = max(0.0, balance.pending_days - app.total_days)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid decision. Must be APPROVE or REJECT.")

        app.decided_at = datetime.now(timezone.utc)
        app.approver_id = approver.id
        app.approver_comments = comments

        # Audit
        audit = AuditLog(
            actor_id=approver.id,
            action=f"LEAVE_{decision}",
            resource_type="leave_application",
            resource_id=app.id,
            details={"decision": decision, "comments": comments}
        )
        db.add(audit)
        await db.commit()
        await db.refresh(app)
        return app

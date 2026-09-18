import csv
import io
from datetime import date, datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.user import User, UserRole, AuditLog
from app.models.timesheet import Project, TimesheetEntry, TimesheetStatus
from app.schemas.timesheet import (
    TimesheetEntryCreate, TimesheetReportFilter, TimesheetReportSummary, TimesheetEntryResponse
)

class TimesheetService:
    @staticmethod
    async def log_entry(
        db: AsyncSession, user: User, data: TimesheetEntryCreate
    ) -> TimesheetEntry:
        # 1. Check Project exists and is active
        proj_stmt = select(Project).filter(Project.id == data.project_id, Project.is_active == True)
        proj_res = await db.execute(proj_stmt)
        project = proj_res.scalars().first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active project not found.")

        # 2. Validate total daily hours across all tasks does not exceed 16 hours
        daily_stmt = select(func.coalesce(func.sum(TimesheetEntry.hours), 0.0)).filter(
            TimesheetEntry.user_id == user.id,
            TimesheetEntry.entry_date == data.entry_date
        )
        daily_res = await db.execute(daily_stmt)
        current_daily_hours = daily_res.scalar() or 0.0

        if (current_daily_hours + data.hours) > 16.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Daily limit exceeded: Logged {current_daily_hours} hrs. Adding {data.hours} hrs exceeds 16 hrs/day cap."
            )

        # 3. Check duplicate entry (same project, task, and date)
        dup_stmt = select(TimesheetEntry).filter(
            TimesheetEntry.user_id == user.id,
            TimesheetEntry.project_id == data.project_id,
            TimesheetEntry.task_name == data.task_name,
            TimesheetEntry.entry_date == data.entry_date
        )
        dup_res = await db.execute(dup_stmt)
        if dup_res.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate timesheet entry: A record for this project, task, and date already exists."
            )

        entry = TimesheetEntry(
            user_id=user.id,
            project_id=data.project_id,
            task_name=data.task_name,
            entry_date=data.entry_date,
            hours=data.hours,
            is_billable=data.is_billable,
            notes=data.notes,
            status=TimesheetStatus.SUBMITTED
        )
        db.add(entry)
        
        audit = AuditLog(
            actor_id=user.id,
            action="TIMESHEET_LOG",
            resource_type="timesheet_entry",
            resource_id=entry.id,
            details={
                "project": project.name,
                "task": data.task_name,
                "date": str(data.entry_date),
                "hours": data.hours
            }
        )
        db.add(audit)
        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def decide_entries(
        db: AsyncSession, approver: User, entry_ids: List[str], decision: str, reason: Optional[str] = None
    ) -> List[TimesheetEntry]:
        if approver.role not in [UserRole.HR_MANAGER, UserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only HR Managers or Admins are authorized to approve/reject timesheets."
            )

        stmt = select(TimesheetEntry).filter(TimesheetEntry.id.in_(entry_ids))
        res = await db.execute(stmt)
        entries = res.scalars().all()
        
        if not entries:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching timesheet entries found.")

        updated_entries = []
        new_status = TimesheetStatus.APPROVED if decision == "APPROVE" else TimesheetStatus.REJECTED
        
        for e in entries:
            e.status = new_status
            e.approver_id = approver.id
            if decision == "REJECT":
                e.rejection_reason = reason
            updated_entries.append(e)

        audit = AuditLog(
            actor_id=approver.id,
            action=f"TIMESHEET_{decision}",
            resource_type="timesheet_batch",
            resource_id=",".join(entry_ids),
            details={"count": len(updated_entries), "decision": decision}
        )
        db.add(audit)
        await db.commit()
        return updated_entries

    @staticmethod
    async def get_report_summary(
        db: AsyncSession, filters: TimesheetReportFilter, requesting_user: User
    ) -> TimesheetReportSummary:
        # Authorization: regular employee can only see their own timesheets
        user_filter = filters.user_id
        if requesting_user.role == UserRole.EMPLOYEE:
            user_filter = requesting_user.id

        query = select(TimesheetEntry).options(
            selectinload(TimesheetEntry.project),
            selectinload(TimesheetEntry.user)
        )
        conditions = []
        
        if user_filter:
            conditions.append(TimesheetEntry.user_id == user_filter)
        if filters.project_id:
            conditions.append(TimesheetEntry.project_id == filters.project_id)
        if filters.status:
            conditions.append(TimesheetEntry.status == filters.status)
        if filters.start_date:
            conditions.append(TimesheetEntry.entry_date >= filters.start_date)
        if filters.end_date:
            conditions.append(TimesheetEntry.entry_date <= filters.end_date)

        if conditions:
            query = query.filter(and_(*conditions))

        query = query.order_by(TimesheetEntry.entry_date.desc())
        result = await db.execute(query)
        entries = result.scalars().all()

        total_hours = sum(e.hours for e in entries)
        billable_hours = sum(e.hours for e in entries if e.is_billable)
        non_billable_hours = total_hours - billable_hours

        entry_responses = [
            TimesheetEntryResponse(
                id=e.id,
                user_id=e.user_id,
                employee_name=e.user.full_name if e.user else None,
                project_id=e.project_id,
                project_name=e.project.name if e.project else None,
                task_name=e.task_name,
                entry_date=e.entry_date,
                hours=e.hours,
                is_billable=e.is_billable,
                notes=e.notes,
                status=e.status,
                approver_id=e.approver_id,
                rejection_reason=e.rejection_reason,
                created_at=e.created_at
            )
            for e in entries
        ]

        return TimesheetReportSummary(
            total_hours=total_hours,
            billable_hours=billable_hours,
            non_billable_hours=non_billable_hours,
            entry_count=len(entries),
            entries=entry_responses
        )

    @staticmethod
    def generate_csv(report: TimesheetReportSummary) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Entry ID", "Employee", "Project", "Task", "Date", "Hours", "Billable", "Status", "Notes"
        ])
        for item in report.entries:
            writer.writerow([
                item.id,
                item.employee_name or item.user_id,
                item.project_name or item.project_id,
                item.task_name,
                str(item.entry_date),
                item.hours,
                "Yes" if item.is_billable else "No",
                item.status.value,
                item.notes or ""
            ])
        return output.getvalue()

import asyncio
from datetime import date, timedelta
from sqlalchemy.future import select

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User, EmployeeProfile, UserRole, OnboardingStatus
from app.models.leave import LeaveBalance, LeaveApplication, LeaveType, LeaveStatus
from app.models.timesheet import Project, TimesheetEntry, TimesheetStatus

async def seed_initial_data():
    async with AsyncSessionLocal() as db:
        # 1. Seed Users if not existing
        res = await db.execute(select(User).filter(User.email == "admin@intelera.corp"))
        if res.scalars().first():
            return # Already seeded

        # Admin
        admin = User(
            email="admin@intelera.corp",
            hashed_password=get_password_hash("Admin@12345"),
            full_name="Devansh Tyagi",
            role=UserRole.ADMIN,
            department="Executive Management",
            designation="Chief Technology Officer"
        )
        db.add(admin)
        await db.flush()

        # HR Manager
        manager = User(
            email="manager@intelera.corp",
            hashed_password=get_password_hash("Manager@12345"),
            full_name="Vikram Malhotra",
            role=UserRole.HR_MANAGER,
            department="Human Resources",
            designation="HR Operations Manager",
            manager_id=admin.id
        )
        db.add(manager)
        await db.flush()

        # HR Associate
        associate = User(
            email="associate@intelera.corp",
            hashed_password=get_password_hash("Associate@12345"),
            full_name="Priya Patel",
            role=UserRole.HR_ASSOCIATE,
            department="Human Resources",
            designation="HR Operations Associate",
            manager_id=manager.id
        )
        db.add(associate)
        await db.flush()

        # Employee
        employee = User(
            email="employee@intelera.corp",
            hashed_password=get_password_hash("Employee@12345"),
            full_name="Aarav Sharma",
            role=UserRole.EMPLOYEE,
            department="Engineering",
            designation="Senior Software Engineer",
            manager_id=manager.id
        )
        db.add(employee)
        await db.flush()

        # Profiles
        emp_profile = EmployeeProfile(
            user_id=employee.id,
            date_of_birth="1995-08-15",
            address_encrypted="102 Horizon Towers, BKC, Mumbai, Maharashtra 400051",
            phone_encrypted="+91 98765 43210",
            skills=["Python", "FastAPI", "React", "PostgreSQL", "Google Cloud"],
            experience_years=5.5,
            employment_type="Full-Time Permanent",
            onboarding_status=OnboardingStatus.COMPLETED
        )
        db.add(emp_profile)

        # 2. Seed Projects
        p1 = Project(name="Core Banking Modernization", code="PROJ-BNK-01", client_name="HDFC Financial")
        p2 = Project(name="AI Observability & Guardrails Platform", code="PROJ-AI-02", client_name="Intelera Internal")
        p3 = Project(name="Enterprise HR Workflow", code="PROJ-HR-03", client_name="Internal Corporate")
        db.add_all([p1, p2, p3])
        await db.flush()

        # 3. Seed Leave Balances for Aarav Sharma (2026)
        b_el = LeaveBalance(user_id=employee.id, year=2026, leave_type=LeaveType.EL, total_allocated=18.0, used_days=2.0, pending_days=0.0, carry_forwarded=3.0)
        b_cl = LeaveBalance(user_id=employee.id, year=2026, leave_type=LeaveType.CL, total_allocated=8.0, used_days=1.0, pending_days=0.0, carry_forwarded=0.0)
        b_sl = LeaveBalance(user_id=employee.id, year=2026, leave_type=LeaveType.SL, total_allocated=10.0, used_days=0.0, pending_days=0.0, carry_forwarded=2.0)
        b_lwp = LeaveBalance(user_id=employee.id, year=2026, leave_type=LeaveType.LWP, total_allocated=0.0, used_days=0.0, pending_days=0.0, carry_forwarded=0.0)
        db.add_all([b_el, b_cl, b_sl, b_lwp])

        # 4. Sample Leave Applications
        app1 = LeaveApplication(
            user_id=employee.id,
            leave_type=LeaveType.EL,
            start_date=date(2026, 2, 10),
            end_date=date(2026, 2, 11),
            total_days=2.0,
            reason="Family commitment in Pune",
            status=LeaveStatus.APPROVED,
            approver_id=manager.id
        )
        app2 = LeaveApplication(
            user_id=employee.id,
            leave_type=LeaveType.CL,
            start_date=date(2026, 3, 5),
            end_date=date(2026, 3, 5),
            total_days=1.0,
            reason="Personal errand",
            status=LeaveStatus.APPROVED,
            approver_id=manager.id
        )
        db.add_all([app1, app2])

        # 5. Sample Timesheets
        t1 = TimesheetEntry(
            user_id=employee.id,
            project_id=p1.id,
            task_name="API Gateway & Auth Integration",
            entry_date=date.today() - timedelta(days=2),
            hours=8.0,
            is_billable=True,
            status=TimesheetStatus.APPROVED,
            approver_id=manager.id
        )
        t2 = TimesheetEntry(
            user_id=employee.id,
            project_id=p2.id,
            task_name="NeMo Guardrails Input Validation Setup",
            entry_date=date.today() - timedelta(days=1),
            hours=7.5,
            is_billable=True,
            status=TimesheetStatus.SUBMITTED
        )
        db.add_all([t1, t2])

        await db.commit()

if __name__ == "__main__":
    asyncio.run(seed_initial_data())

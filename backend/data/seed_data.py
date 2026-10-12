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
        res = await db.execute(select(User).filter(User.email == "devansh.tyagi@intelera.com"))
        if res.scalars().first():
            return # Already seeded

        # Admin / CTO
        admin = User(
            id="EMP-001",
            email="devansh.tyagi@intelera.com",
            hashed_password=get_password_hash("password123"),
            full_name="Devansh Tyagi",
            role=UserRole.ADMIN,
            department="Executive Management",
            designation="Chief Technology Officer"
        )
        db.add(admin)
        await db.flush()

        # HR Manager
        manager = User(
            id="EMP-002",
            email="vikram.malhotra@intelera.com",
            hashed_password=get_password_hash("password123"),
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
            id="EMP-003",
            email="priya.patel@intelera.com",
            hashed_password=get_password_hash("password123"),
            full_name="Priya Patel",
            role=UserRole.HR_ASSOCIATE,
            department="Human Resources",
            designation="HR Operations Associate",
            manager_id=manager.id
        )
        db.add(associate)
        await db.flush()

        # Senior Software Engineer
        employee = User(
            id="EMP-004",
            email="aarav.sharma@intelera.com",
            hashed_password=get_password_hash("password123"),
            full_name="Aarav Sharma",
            role=UserRole.EMPLOYEE,
            department="Engineering",
            designation="Senior Software Engineer",
            manager_id=admin.id
        )
        db.add(employee)
        await db.flush()

        # Operations Associate
        employee2 = User(
            id="EMP-005",
            email="sneha.kulkarni@intelera.com",
            hashed_password=get_password_hash("password123"),
            full_name="Sneha Kulkarni",
            role=UserRole.EMPLOYEE,
            department="Operations",
            designation="Operations Associate",
            manager_id=manager.id
        )
        db.add(employee2)
        await db.flush()

        # Profiles
        emp_profile = EmployeeProfile(
            id="prf_aarav.sharma",
            user_id=employee.id,
            date_of_birth="1995-08-15",
            address_encrypted="102 Horizon Towers, BKC, Mumbai 400051",
            phone_encrypted="+91 98765 43210",
            skills=["Python", "FastAPI", "React", "PostgreSQL", "Google Cloud"],
            experience_years=5.5,
            employment_type="Full-Time",
            onboarding_status=OnboardingStatus.COMPLETED
        )
        db.add(emp_profile)

        # 2. Seed Projects
        p1 = Project(id="prj_hdfc_banking", name="Core Banking Modernization", code="PRJ-BNK-01", client_name="HDFC Financial")
        p2 = Project(id="prj_ai_guardrails", name="AI Observability & Guardrails", code="PRJ-AI-02", client_name="Intelera Platform")
        p3 = Project(id="prj_internal_ops", name="Internal Operations & Compliance", code="PRJ-OPS-03", client_name="Intelera Internal")
        db.add_all([p1, p2, p3])
        await db.flush()

        # 3. Seed Leave Balances for Aarav Sharma (2026)
        b_el = LeaveBalance(id="bal_aarav.sharma_el", user_id=employee.id, year=2026, leave_type=LeaveType.EL, total_allocated=18.0, used_days=2.0, pending_days=0.0, carry_forwarded=3.0)
        b_cl = LeaveBalance(id="bal_aarav.sharma_cl", user_id=employee.id, year=2026, leave_type=LeaveType.CL, total_allocated=8.0, used_days=1.0, pending_days=0.0, carry_forwarded=0.0)
        b_sl = LeaveBalance(id="bal_aarav.sharma_sl", user_id=employee.id, year=2026, leave_type=LeaveType.SL, total_allocated=10.0, used_days=0.0, pending_days=0.0, carry_forwarded=2.0)
        b_lwp = LeaveBalance(id="bal_aarav.sharma_lwp", user_id=employee.id, year=2026, leave_type=LeaveType.LWP, total_allocated=0.0, used_days=0.0, pending_days=0.0, carry_forwarded=0.0)
        db.add_all([b_el, b_cl, b_sl, b_lwp])

        # 4. Sample Leave Applications
        app1 = LeaveApplication(
            id="leave_aarav.sharma_1",
            user_id=employee.id,
            leave_type=LeaveType.EL,
            start_date=date(2026, 2, 10),
            end_date=date(2026, 2, 11),
            total_days=2.0,
            reason="Annual Family Vacation (Pune)",
            status=LeaveStatus.APPROVED,
            approver_id=manager.id
        )
        app2 = LeaveApplication(
            id="leave_aarav.sharma_2",
            user_id=employee.id,
            leave_type=LeaveType.CL,
            start_date=date(2026, 3, 5),
            end_date=date(2026, 3, 5),
            total_days=1.0,
            reason="Personal Banking & Legal Errand",
            status=LeaveStatus.APPROVED,
            approver_id=manager.id
        )
        db.add_all([app1, app2])

        # 5. Sample Timesheets
        t1 = TimesheetEntry(
            id="ts_aarav.sharma_1",
            user_id=employee.id,
            project_id=p1.id,
            task_name="API Gateway & OAuth 2.0 Integration",
            entry_date=date.today() - timedelta(days=2),
            hours=8.0,
            is_billable=True,
            status=TimesheetStatus.APPROVED,
            approver_id=manager.id
        )
        t2 = TimesheetEntry(
            id="ts_aarav.sharma_2",
            user_id=employee.id,
            project_id=p2.id,
            task_name="NeMo Guardrails & Input Validation Setup",
            entry_date=date.today() - timedelta(days=1),
            hours=7.5,
            is_billable=True,
            status=TimesheetStatus.SUBMITTED
        )
        db.add_all([t1, t2])

        await db.commit()

if __name__ == "__main__":
    asyncio.run(seed_initial_data())

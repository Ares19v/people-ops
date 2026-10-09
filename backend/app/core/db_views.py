"""
PeopleOps — Clean PostgreSQL SQL Views & Database Inspector Engine
===================================================================
Provides high-performance, human-readable SQL Views and inspection
endpoints to browse clean relational views and underlying tables.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import engine

SQL_VIEWS = {
    "v_employees_overview": {
        "title": "Employees Overview",
        "description": "Unified view of active employees, departments, managers, and onboarding status.",
        "icon": "Users",
        "category": "Core HR",
        "sql": """
            CREATE OR REPLACE VIEW v_employees_overview AS
            SELECT 
                u.id AS employee_id,
                u.full_name,
                u.email,
                u.role,
                u.department,
                u.designation,
                COALESCE(m.full_name, 'None (Executive)') AS manager_name,
                p.employment_type,
                p.experience_years,
                p.onboarding_status,
                u.is_active,
                TO_CHAR(u.created_at, 'YYYY-MM-DD HH24:MI') AS joined_date
            FROM users u
            LEFT JOIN users m ON u.manager_id = m.id
            LEFT JOIN employee_profiles p ON u.id = p.user_id
            ORDER BY u.created_at ASC;
        """
    },
    "v_leaves_summary": {
        "title": "Leave Applications",
        "description": "Clean ledger of all leave requests, dates, approvers, and statuses.",
        "icon": "Calendar",
        "category": "Time & Absence",
        "sql": """
            CREATE OR REPLACE VIEW v_leaves_summary AS
            SELECT 
                la.id AS application_id,
                u.id AS employee_id,
                u.full_name AS applicant_name,
                u.department,
                la.leave_type,
                TO_CHAR(la.start_date, 'YYYY-MM-DD') AS start_date,
                TO_CHAR(la.end_date, 'YYYY-MM-DD') AS end_date,
                la.total_days,
                la.reason,
                la.status,
                COALESCE(mgr.full_name, 'Pending / System') AS approver_name,
                TO_CHAR(la.applied_at, 'YYYY-MM-DD HH24:MI') AS submitted_at
            FROM leave_applications la
            JOIN users u ON la.user_id = u.id
            LEFT JOIN users mgr ON la.approver_id = mgr.id
            ORDER BY la.applied_at DESC;
        """
    },
    "v_leave_balances_overview": {
        "title": "Leave Balances Ledger",
        "description": "Calculated remaining balances per employee and leave quota type.",
        "icon": "PieChart",
        "category": "Time & Absence",
        "sql": """
            CREATE OR REPLACE VIEW v_leave_balances_overview AS
            SELECT 
                lb.id AS balance_id,
                u.id AS employee_id,
                u.full_name AS employee_name,
                lb.year,
                lb.leave_type,
                lb.total_allocated,
                lb.used_days,
                lb.pending_days,
                lb.carry_forwarded,
                (lb.total_allocated + lb.carry_forwarded - lb.used_days - lb.pending_days) AS remaining_balance
            FROM leave_balances lb
            JOIN users u ON lb.user_id = u.id
            ORDER BY u.full_name, lb.leave_type;
        """
    },
    "v_timesheets_active": {
        "title": "Timesheets & Hours",
        "description": "Project hour logging, billable status, and manager approvals.",
        "icon": "Clock",
        "category": "Project Tracking",
        "sql": """
            CREATE OR REPLACE VIEW v_timesheets_active AS
            SELECT 
                ts.id AS timesheet_id,
                u.id AS employee_id,
                u.full_name AS employee_name,
                p.name AS project_name,
                p.code AS project_code,
                ts.task_name,
                TO_CHAR(ts.entry_date, 'YYYY-MM-DD') AS entry_date,
                ts.hours,
                ts.is_billable,
                ts.status,
                COALESCE(mgr.full_name, 'Auto / Pending') AS approver_name
            FROM timesheet_entries ts
            JOIN users u ON ts.user_id = u.id
            JOIN projects p ON ts.project_id = p.id
            LEFT JOIN users mgr ON ts.approver_id = mgr.id
            ORDER BY ts.entry_date DESC;
        """
    },
    "v_chat_sessions_overview": {
        "title": "AI Conversational Sessions",
        "description": "Session tracking, turn counts, and user interaction timestamps.",
        "icon": "MessageSquare",
        "category": "AI & Observability",
        "sql": """
            CREATE OR REPLACE VIEW v_chat_sessions_overview AS
            SELECT 
                cs.id AS session_id,
                COALESCE(u.full_name, 'Anonymous / Guest') AS user_name,
                cs.title AS session_title,
                COUNT(ct.id) AS total_turns,
                TO_CHAR(cs.created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                TO_CHAR(cs.updated_at, 'YYYY-MM-DD HH24:MI') AS last_active
            FROM chat_sessions cs
            LEFT JOIN users u ON cs.user_id = u.id
            LEFT JOIN chat_turns ct ON cs.id = ct.session_id
            GROUP BY cs.id, u.full_name, cs.title, cs.created_at, cs.updated_at
            ORDER BY cs.updated_at DESC;
        """
    },
    "v_chat_turns_recent": {
        "title": "Recent AI Messages & Turns",
        "description": "Turn-by-turn dialogue snippets, roles, and latency records.",
        "icon": "Terminal",
        "category": "AI & Observability",
        "sql": """
            CREATE OR REPLACE VIEW v_chat_turns_recent AS
            SELECT 
                ct.id AS turn_id,
                ct.session_id,
                ct.role,
                ct.content,
                TO_CHAR(ct.created_at, 'YYYY-MM-DD HH24:MI:SS') AS timestamp
            FROM chat_turns ct
            ORDER BY ct.created_at DESC;
        """
    },
    "v_zoho_sync_history": {
        "title": "Zoho HRMS Sync Ledger",
        "description": "External sync audit records, payloads, and status codes.",
        "icon": "RefreshCw",
        "category": "External Integrations",
        "sql": """
            CREATE OR REPLACE VIEW v_zoho_sync_history AS
            SELECT 
                zr.id AS sync_id,
                zr.user_id,
                zr.record_type,
                zr.zoho_record_id,
                zr.status,
                TO_CHAR(zr.created_at, 'YYYY-MM-DD HH24:MI') AS synced_at
            FROM zoho_sync_records zr
            ORDER BY zr.created_at DESC;
        """
    }
}


async def initialize_database_views():
    """Executes DDL to ensure all clean SQL views are up to date on database startup."""
    try:
        async with engine.begin() as conn:
            for view_key, view_meta in SQL_VIEWS.items():
                await conn.execute(text(f"DROP VIEW IF EXISTS {view_key} CASCADE;"))
                await conn.execute(text(view_meta["sql"]))
        print("[DB Views] All clean SQL Views successfully initialized.")
    except Exception as e:
        print(f"[DB Views] Notice initializing views: {e}")


async def get_available_views_metadata(db: AsyncSession) -> List[Dict[str, Any]]:
    """Returns all available SQL views and their row counts."""
    results = []
    for key, meta in SQL_VIEWS.items():
        count = 0
        try:
            res = await db.execute(text(f"SELECT COUNT(*) FROM {key};"))
            count = res.scalar() or 0
        except Exception:
            await db.rollback()
            count = 0
        results.append({
            "key": key,
            "title": meta["title"],
            "description": meta["description"],
            "icon": meta["icon"],
            "category": meta["category"],
            "rowCount": count
        })
    return results


async def fetch_view_records(db: AsyncSession, view_name: str, search: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """Fetches formatted records and column headers for a given view."""
    if view_name not in SQL_VIEWS:
        raise ValueError(f"View '{view_name}' is not recognized or permitted.")

    where_clause = ""
    params: Dict[str, Any] = {}

    if search and search.strip():
        where_clause = " WHERE CAST(row_to_json(t) AS TEXT) ILIKE :search"
        params["search"] = f"%{search.strip()}%"

    full_sql = f"SELECT * FROM {view_name} AS t {where_clause} LIMIT {limit}"

    res = await db.execute(text(full_sql), params)
    rows = [dict(row._mapping) for row in res.fetchall()]
    # Ensure serializable types
    for r in rows:
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
            elif hasattr(v, "value"):  # Enum
                r[k] = v.value
    columns = list(rows[0].keys()) if rows else []

    return {
        "view_name": view_name,
        "meta": SQL_VIEWS[view_name],
        "columns": columns,
        "rows": rows,
        "total_returned": len(rows)
    }

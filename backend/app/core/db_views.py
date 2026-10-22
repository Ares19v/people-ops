"""
PeopleOps — Database Inspector & Query Engine
=============================================
Provides clean, direct relational queries for the visual inspector
without polluting the database schema with redundant SQL views.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import engine

logger = logging.getLogger(__name__)

INSPECTOR_QUERIES = {
    "v_employees_overview": {
        "title": "Employees Overview",
        "description": "Unified view of active employees, departments, managers, and onboarding status.",
        "icon": "Users",
        "category": "Core HR",
        "query": """
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
                u.created_at AS joined_date
            FROM users u
            LEFT JOIN users m ON u.manager_id = m.id
            LEFT JOIN employee_profiles p ON u.id = p.user_id
            ORDER BY u.id ASC
        """
    },
    "v_leave_summary_compact": {
        "title": "Employee Leave Balances (Consolidated)",
        "description": "One concise row per employee showing current EL, CL, SL, and total available balances.",
        "icon": "PieChart",
        "category": "Time & Absence",
        "query": """
            SELECT 
                u.id AS employee_id,
                u.full_name AS employee_name,
                u.department,
                COALESCE(MAX(CASE WHEN lb.leave_type = 'EL' THEN (lb.total_allocated + lb.carry_forwarded - lb.used_days - lb.pending_days) END), 0) AS earned_leave_el,
                COALESCE(MAX(CASE WHEN lb.leave_type = 'CL' THEN (lb.total_allocated - lb.used_days - lb.pending_days) END), 0) AS casual_leave_cl,
                COALESCE(MAX(CASE WHEN lb.leave_type = 'SL' THEN (lb.total_allocated - lb.used_days - lb.pending_days) END), 0) AS sick_leave_sl,
                COALESCE(SUM(lb.total_allocated + lb.carry_forwarded - lb.used_days - lb.pending_days), 0) AS total_available_days,
                COALESCE(SUM(lb.used_days), 0) AS total_used_days
            FROM users u
            LEFT JOIN leave_balances lb ON u.id = lb.user_id
            GROUP BY u.id, u.full_name, u.department
            ORDER BY u.id ASC
        """
    },
    "v_leaves_summary": {
        "title": "Leave Applications",
        "description": "Clean ledger of all leave requests, dates, approvers, and statuses.",
        "icon": "Calendar",
        "category": "Time & Absence",
        "query": """
            SELECT 
                la.id AS application_id,
                u.id AS employee_id,
                u.full_name AS applicant_name,
                u.department,
                la.leave_type,
                la.start_date,
                la.end_date,
                la.total_days,
                la.reason,
                la.status,
                COALESCE(mgr.full_name, 'Pending / System') AS approver_name,
                la.applied_at AS submitted_at
            FROM leave_applications la
            JOIN users u ON la.user_id = u.id
            LEFT JOIN users mgr ON la.approver_id = mgr.id
            ORDER BY la.applied_at DESC
        """
    },
    "v_leave_balances_overview": {
        "title": "Leave Balances (Detailed Quotas)",
        "description": "Calculated remaining balances per employee and leave quota type.",
        "icon": "PieChart",
        "category": "Time & Absence",
        "query": """
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
            ORDER BY u.id, lb.leave_type
        """
    },
    "v_timesheets_active": {
        "title": "Timesheets & Hours",
        "description": "Project hour logging, billable status, and manager approvals.",
        "icon": "Clock",
        "category": "Project Tracking",
        "query": """
            SELECT 
                ts.id AS timesheet_id,
                u.id AS employee_id,
                u.full_name AS employee_name,
                p.name AS project_name,
                p.code AS project_code,
                ts.task_name,
                ts.entry_date,
                ts.hours,
                ts.is_billable,
                ts.status,
                COALESCE(mgr.full_name, 'Auto / Pending') AS approver_name,
                ts.created_at AS logged_at
            FROM timesheet_entries ts
            JOIN users u ON ts.user_id = u.id
            JOIN employee_projects p ON ts.project_id = p.id
            LEFT JOIN users mgr ON ts.approver_id = mgr.id
            ORDER BY ts.created_at DESC, ts.entry_date DESC
        """
    },
    "v_employee_documents": {
        "title": "Uploaded Documents & PDFs",
        "description": "Employee onboarding PDFs, Aadhaar, PAN, and Resume verification records (latest to oldest).",
        "icon": "TableIcon",
        "category": "Core HR",
        "query": """
            SELECT 
                d.id AS document_id,
                u.id AS employee_id,
                u.full_name AS employee_name,
                d.doc_type,
                d.original_filename,
                d.mime_type,
                d.file_size,
                d.is_verified,
                d.created_at AS uploaded_at
            FROM employee_documents d
            JOIN users u ON d.user_id = u.id
            ORDER BY d.created_at DESC
        """
    },
    "v_chat_sessions_overview": {
        "title": "AI Conversational Sessions",
        "description": "Session tracking, turn counts, and user interaction timestamps.",
        "icon": "MessageSquare",
        "category": "AI & Observability",
        "query": """
            SELECT 
                cs.id AS session_id,
                COALESCE(u.full_name, 'Anonymous / Guest') AS user_name,
                cs.title AS session_title,
                COUNT(ct.id) AS total_turns,
                cs.created_at,
                cs.updated_at AS last_active
            FROM chat_sessions cs
            LEFT JOIN users u ON cs.user_id = u.id
            LEFT JOIN chat_turns ct ON cs.id = ct.session_id
            GROUP BY cs.id, u.full_name, cs.title, cs.created_at, cs.updated_at
            ORDER BY cs.updated_at DESC, cs.created_at DESC
        """
    },
    "v_chat_turns_recent": {
        "title": "Recent AI Messages & Turns",
        "description": "Turn-by-turn dialogue snippets, roles, and latency records.",
        "icon": "Terminal",
        "category": "AI & Observability",
        "query": """
            SELECT 
                ct.id AS turn_id,
                ct.session_id,
                ct.role,
                ct.content,
                ct.created_at AS timestamp
            FROM chat_turns ct
            ORDER BY ct.created_at DESC
        """
    },
    "v_conversation_summaries": {
        "title": "Rolling Session Summaries (Memory Window)",
        "description": "Cross-session memory summaries (sliding window of 5) stored in PostgreSQL for reinjection.",
        "icon": "MessageSquare",
        "category": "AI & Observability",
        "query": """
            SELECT 
                s.id AS summary_id,
                COALESCE(s.user_email, u.email, s.user_id) AS user_email,
                s.session_id,
                s.session_title,
                s.summary_text,
                s.pending_action,
                s.covers_turns_count,
                s.created_at
            FROM conversation_summaries s
            LEFT JOIN users u ON s.user_id = u.id
            ORDER BY s.created_at DESC
        """
    },
    "v_security_audit_trail": {
        "title": "Security & DPDP Audit Trail",
        "description": "Immutable ledger of leave, timesheet, and onboarding actions (latest to oldest).",
        "icon": "Terminal",
        "category": "Core HR",
        "query": """
            SELECT 
                st.id AS audit_id,
                COALESCE(u.full_name, st.actor_id, 'System') AS actor_name,
                st.action,
                st.resource_type,
                st.resource_id,
                st.created_at AS timestamp
            FROM security_trail st
            LEFT JOIN users u ON st.actor_id = u.id
            ORDER BY st.created_at DESC
        """
    },
    "v_zoho_sync_history": {
        "title": "Zoho HRMS Sync Ledger",
        "description": "External sync audit records, payloads, and status codes.",
        "icon": "RefreshCw",
        "category": "External Integrations",
        "query": """
            SELECT 
                zr.id AS sync_id,
                u.full_name AS employee_name,
                zr.record_type,
                zr.zoho_record_id,
                zr.status,
                zr.created_at AS synced_at
            FROM zoho_sync_records zr
            JOIN users u ON zr.user_id = u.id
            ORDER BY zr.created_at DESC
        """
    },
    "v_agent_prompts": {
        "title": "Agent Prompts & Langfuse Sync",
        "description": "Multi-tier prompt ledger synced across PostgreSQL, Langfuse Cloud, and ADK Fleet.",
        "icon": "Terminal",
        "category": "AI & Observability",
        "query": """
            SELECT 
                p.prompt_key,
                p.agent_name,
                p.version,
                p.label,
                p.is_active,
                p.updated_at,
                SUBSTRING(p.template, 1, 250) AS template_preview
            FROM agent_prompts p
            ORDER BY p.updated_at DESC
        """
    }
}

# Alias for backwards compatibility
SQL_VIEWS = INSPECTOR_QUERIES


async def initialize_database_views():
    """Cleans up any legacy database views to keep the database schema concise."""
    legacy_views = [
        "v_employees_overview",
        "v_leave_summary_compact",
        "v_leaves_summary",
        "v_leave_balances_overview",
        "v_timesheets_active",
        "v_chat_sessions_overview",
        "v_chat_turns_recent",
        "v_zoho_sync_history",
    ]
    try:
        async with engine.begin() as conn:
            for view_key in legacy_views:
                await conn.execute(text(f"DROP VIEW IF EXISTS {view_key} CASCADE;"))
    except Exception:
        logger.debug("Suppressed non-fatal error", exc_info=True)


async def get_available_views_metadata(db: AsyncSession) -> List[Dict[str, Any]]:
    """Returns all available inspector reports and their row counts."""
    results = []
    for key, meta in INSPECTOR_QUERIES.items():
        count = 0
        try:
            count_sql = f"SELECT COUNT(*) FROM ({meta['query']}) AS subq"
            res = await db.execute(text(count_sql))
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
    """Fetches formatted records and column headers for a given report query."""
    if view_name not in INSPECTOR_QUERIES:
        raise ValueError(f"Report '{view_name}' is not recognized or permitted.")

    meta = INSPECTOR_QUERIES[view_name]
    base_query = meta["query"]

    # When inspecting prompts, auto-detect any changes made in TablePlus / DB and sync to Langfuse
    if view_name == "v_agent_prompts":
        try:
            from app.services.langfuse_prompt_service import (
                ENABLE_POSTGRES_TO_LANGFUSE_SYNC, langfuse_prompt_service, ManagedPrompt,
            )
            from app.models.prompt import AgentPrompt
            from app.agents.adk_fleet import sync_agent_instructions
            import time

            stmt = select(AgentPrompt)
            p_res = await db.execute(stmt)
            p_records = p_res.scalars().all()
            changed = []
            with langfuse_prompt_service._lock:
                for r in (p_records if ENABLE_POSTGRES_TO_LANGFUSE_SYNC else []):
                    cached = langfuse_prompt_service._cache.get(r.prompt_key)
                    if not cached or cached.template != r.template:
                        langfuse_prompt_service._cache[r.prompt_key] = ManagedPrompt(
                            name=r.prompt_key,
                            version=str(r.version),
                            template=r.template,
                            label=r.label,
                            source="database",
                            fetched_at=time.time(),
                        )
                        changed.append(r)
            if changed:
                sync_agent_instructions()
                if langfuse_prompt_service._langfuse_client:
                    for ch_r in changed:
                        try:
                            lf_p = langfuse_prompt_service._langfuse_client.create_prompt(
                                name=ch_r.prompt_key,
                                prompt=ch_r.template,
                                labels=["live", "production"],
                                type="text",
                                tags=["peopleops", "adk-agents"]
                            )
                            new_v = getattr(lf_p, "version", None)
                            if new_v:
                                ch_r.version = new_v
                                with langfuse_prompt_service._lock:
                                    if ch_r.prompt_key in langfuse_prompt_service._cache:
                                        langfuse_prompt_service._cache[ch_r.prompt_key].version = str(new_v)
                        except Exception as e:
                            logger.warning(f"Notice: Auto-pushing view prompt change to Langfuse: {e}")
                    await db.commit()
        except Exception as e:
            logger.warning(f"Notice: v_agent_prompts auto-sync check: {e}")

    full_sql = f"SELECT * FROM ({base_query}) AS t LIMIT {limit}"

    res = await db.execute(text(full_sql))
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
        "meta": meta,
        "columns": columns,
        "rows": rows,
        "total_returned": len(rows)
    }

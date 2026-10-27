"""Tool: sync_zoho_leave_records (Google ADK compatible tool)."""

import logging
from typing import Any, Dict

from app.core.logging_config import log_tool_call
from app.services.zoho_service import zoho_service

logger = logging.getLogger(__name__)


@log_tool_call
async def sync_zoho_leave_records(user_id: str) -> Dict[str, Any]:
    """Fetch external synchronized leave records from Zoho People HRMS REST API v2.

    Call this at most once per request; it returns every record for the employee.

    Args:
        user_id: The employee ID code from the "ID: ..." part of the [Active Employee ...] header
            (for example EMP-004). Never pass the employee's name, first name or any other text.

    Returns:
        Dict containing synchronized leave records.
    """
    try:
        records = await zoho_service.get_leave_records(user_id)
        formatted = [
            {
                "leave_type": r.leave_type,
                "days": r.days,
                "from_date": r.from_date,
                "to_date": r.to_date,
                "status": r.status,
            }
            for r in records
        ]
        return {
            "user_id": user_id,
            "count": len(formatted),
            "records": formatted,
            "source": "Zoho People REST API v2",
        }
    except Exception as exc:
        return {"error": f"Failed to sync with Zoho People: {str(exc)}"}
